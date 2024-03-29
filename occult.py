#!/usr/bin/env python3

import argparse
import datetime
import os
import logging
import json
import sys
import stat

from abc import ABC, abstractmethod
from urllib.parse import urljoin
from subprocess import Popen, PIPE, DEVNULL
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib3.util.retry import Retry

from requests.adapters import HTTPAdapter
import requests


DEFAULT_BACKOFF_ATTEMPTS = 15
DEFAULT_PROFILE_NAME = "default"
DEFAULT_CONFIG_LOCATION = "~/.occult.conf"
DEFAULT_JSON_VALUE_ACCESSOR = "data.value"
ENV_OCCULT_CONFIG = "OCCULT_CONFIG"


class AuthMethod(ABC):
    """ Defines an auth method to login in to vault. """
    @abstractmethod
    def get_token(self) -> str:
        pass

    @abstractmethod
    def cleanup(self) -> bool:
        pass


class VaultClient:
    """ Interact with Hashicorp Vault. """
    def __init__(self,
                 endpoint: str,
                 auth_method: AuthMethod = None,
                 http_pool: requests.Session = None,
                 secret_mount: str = "secret"):

        self._endpoint = endpoint

        if not auth_method:
            raise ValueError("No auth method provided")
        self.auth_method = auth_method
        self._secret_mount = secret_mount

        if not http_pool:
            http_pool = requests.Session()
        self._http_pool = http_pool

    def authenticate(self) -> Optional[str]:
        logging.info("Trying to authenticate with '%s'", self.auth_method.name)
        return self.auth_method.get_token()

    def read_kv_secret_data(self, token: str, vault_secret_path: str) -> Optional[str]:
        url = urljoin(self._endpoint, f"/v1/{self._secret_mount}/data/{vault_secret_path}")
        resp = self._http_pool.get(headers={'X-Vault-Token': token}, url=url)
        if not resp.ok:
            raise VaultException(f"Couldn't fetch secret, got HTTP {resp.status_code}: {resp.content} for {url}")

        return resp.json()["data"]

    def cleanup(self) -> bool:
        return self.auth_method.cleanup()


class Drone:
    """ Pipes the password to the configured command, runs the post-hook. """
    def __init__(self, cmd: str, post_hooks: List[str] = None, timeout: int = 60):
        if not cmd:
            raise ValueError("No cmd provided")

        if not isinstance(cmd, str):
            raise ValueError("'cmd' is expected to be a string")
        self.cmd = cmd

        if post_hooks and (not isinstance(post_hooks, list) or any(not isinstance(item, str) for item in post_hooks)):
            raise ValueError("'post_hooks' is expected to be a list of strings")
        self.post_hooks = post_hooks

        if timeout < 10 or timeout > 6000:
            raise ValueError("Invalid value for timeout, must be in range [1, 6000]")
        self.timeout = timeout

    def send_password(self, password: str) -> None:
        enc = password.encode('utf-8')
        cmd = self.cmd.split(" ")
        logging.info("Sending password to defined command '%s'", cmd[0])
        with Popen(cmd, stdin=PIPE, stdout=DEVNULL) as proc:
            proc.communicate(input=enc)
            proc.wait(self.timeout)
            if proc.returncode != 0:
                raise CmdNotSuccessfulException()
            logging.info("Sent password to defined cmd '%s'", cmd[0])

    def run_post_hooks(self) -> None:
        if not self.post_hooks:
            return

        for hook in self.post_hooks:
            logging.info("Running post hook cmd '%s'", hook)
            cmd = hook.split(" ")
            try:
                with Popen(cmd, stdout=DEVNULL) as proc:
                    proc.wait(self.timeout)
                    if proc.returncode != 0:
                        logging.error("hook returned exitcode %d", proc.returncode)
            except Exception as err:
                logging.error("error running hook: %s", err)


def start_occult(args: argparse.Namespace, vault_client: VaultClient, drone: Drone) -> None:
    success = False

    try:
        token = vault_client.authenticate()

        logging.info("Trying to read secret '%s'", args.secret_path)
        read_secret = vault_client.read_kv_secret_data(token, args.secret_path)
        logging.info("Successfully read secret from vault")

        logging.info("Trying to extract value from JSON path '%s'", args.json_value_accessor)
        password = Utils.extract_json_value(read_secret, args.json_value_accessor)

        drone.send_password(password)
        drone.run_post_hooks()

        success = True
    except KeyError as err:
        logging.error("No such field found in reply from vault, check json_value_accessor: '%s'", err)
    except VaultException as err:
        logging.error("Error talking to vault: %s", err)
    except FileNotFoundError as err:
        logging.error("No such cmd: %s", err)
    except CmdNotSuccessfulException:
        logging.error("Command unsuccessful")
    except requests.RequestException as err:
        logging.error("Error while talking to vault: %s", err)

    try:
        if not vault_client.cleanup():
            logging.warning("Cleanup not successful")
    except VaultException as err:
        logging.error("Could not increase token lifetime: %s", err)
    except requests.RequestException as err:
        logging.error("Error while talking to vault: %s", err)

    if not args.metrics_file:
        logging.warning("Not writing metrics, no metrics_file specified")
        sys.exit(0)

    logging.info("Writing metrics to %s", args.metrics_file)
    try:
        Utils.write_metrics_file(args.metrics_file, success, args.profile)
    except OSError as err:
        logging.error("Could not write metrics: %s", err)

    if not success:
        sys.exit(1)


class StaticTokenMethod(AuthMethod):
    """ Uses a previously provisioned static vault token. """
    name = "static token"

    def __init__(self, endpoint: str, token: str, http_pool: requests.Session = None):
        self._endpoint = endpoint
        self._token = token
        if not http_pool:
            http_pool = requests.Session()

        self._http_pool = http_pool

    def get_token(self) -> str:
        return self._token

    def cleanup(self) -> bool:
        logging.info("Not cleaning up static token")


class AppRoleMethod(AuthMethod):
    """ Uses the AppRole auth mechanism to acquire token. """
    name = "AppRole"

    def __init__(self,
                 endpoint: str,
                 role_id: str,
                 secret_id: str,
                 http_pool: requests.Session = None,
                 approle_mount: str = "approle"
                 ):
        self._endpoint = endpoint
        self._role_id = role_id
        self._secret_id = secret_id
        self._approle_mount = approle_mount
        self._token = None

        if not http_pool:
            http_pool = requests.Session()
        self._http_pool = http_pool

    @staticmethod
    def from_args(args: argparse.Namespace, http_pool: requests.Session = None) -> AuthMethod:
        return AppRoleMethod(
            endpoint=args.vault_address,
            role_id=args.vault_role_id,
            secret_id=Utils.get_secret_id(args),
            http_pool=http_pool
        )

    def get_token(self) -> str:
        if self._token:
            return self._token

        url = urljoin(self._endpoint, f"/v1/auth/{self._approle_mount}/login")
        data = {
            "role_id": self._role_id,
            "secret_id": self._secret_id
        }
        resp = self._http_pool.post(data=data, url=url)
        if not resp.ok:
            raise VaultException(f"Couldn't login, got HTTP {resp.status_code}: {resp.content}")

        logging.info("Login via AppRole successful")
        content = json.loads(resp.content)
        self._token = content["auth"]["client_token"]
        return self._token

    def cleanup(self) -> bool:
        logging.info("Revoking acquired token")
        url = urljoin(self._endpoint, "/v1/auth/token/revoke-self")
        resp = self._http_pool.post(url=url, headers={'X-Vault-Token': self._token})
        return resp.ok


class ParsingUtils:
    @staticmethod
    def verify_args(args: argparse.Namespace):
        if args.vault_secret_id and args.vault_secret_id_file:
            raise ValueError("Must not specify 'both vault-secret-id' and 'vault-secret-id-file'")

        if not (args.vault_token or args.vault_token_file) and not args.vault_role_id and (not args.vault_secret_id or not args.vault_secret_id_file):
            raise ValueError("Must specify either 'token' or AppRole auth")

        if not args.vault_role_id and (args.vault_secret_id or args.vault_secret_id_file):
            raise ValueError("Must specify 'vault-role-id' if using AppRole auth")

        if (args.vault_token or args.vault_token_file) and args.vault_secret_id:
            raise ValueError("Can not both specify both 'token' and AppRole auth")

        if args.backoff_attempts < 0 or args.backoff_attempts > 50:
            raise ValueError("Backoff attempts must be in range [0, 50]")

    @staticmethod
    def check_config_permissions(config_file: str) -> None:
        file_stat = os.stat(config_file)
        grp_readable = bool(file_stat.st_mode & stat.S_IRGRP)
        world_readable = bool(file_stat.st_mode & stat.S_IRWXG)
        if grp_readable or world_readable:
            raise PermissionError("Config file must not be group/world readable")

    @staticmethod
    def parse_args() -> argparse.Namespace:
        conf_parser = argparse.ArgumentParser(
            description=__doc__,  # printed with -h/--help
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
            # Turn off help, so we print all options in response to -h
            add_help=False,
        )
        conf_parser.add_argument("-c", "--config", default=os.getenv(ENV_OCCULT_CONFIG), help="Specify config file",
                                 metavar="FILE")
        group_args, remaining_argv = conf_parser.parse_known_args()
        config_values = {}

        # check if the user supplied a config or if we should look for the default conf location
        config_file = group_args.config
        if group_args.config:
            config_file = Path(group_args.config).expanduser()
        else:
            default_config_file = Path(DEFAULT_CONFIG_LOCATION).expanduser()
            if default_config_file.is_file():
                config_file = default_config_file

        if config_file:
            try:
                ParsingUtils.check_config_permissions(config_file)
                with open(config_file, encoding="utf-8") as cf:
                    config = json.load(cf)
                    config_values.update(config)
            except json.decoder.JSONDecodeError as err:
                logging.error("Config file is not well formatted: %s", err)
                sys.exit(1)
            except FileNotFoundError:
                logging.error("Config file %s does not exist", group_args.config)
                sys.exit(1)
            except PermissionError:
                logging.error("Config file permissions to liberal")
                sys.exit(1)

        args = argparse.ArgumentParser(parents=[conf_parser])

        args.add_argument("--vault-address", help="The vault instance to connect to",
                          required="vault_address" not in config_values)
        args.add_argument("--vault-token", help="The vault token")
        args.add_argument("--vault-token-file", help="Flat file to read the vault token from.")
        args.add_argument("--vault-role-id", help="The role_id to login to the AppRole")
        args.add_argument("-q", "--quiet", help="Be quiet.", action="store_true")
        args.add_argument("-b", "--backoff-attempts", type=int, default=DEFAULT_BACKOFF_ATTEMPTS,
                          help="How often to try retry a operation")

        group = args.add_mutually_exclusive_group()
        group.add_argument("--vault-secret-id", help="The secret_id to login to the AppRole")
        group.add_argument("--vault-secret-id-file", help="Read secret_id from a flat file")
        group.set_defaults(**config_values)

        args.add_argument("-j", "--json-value-accessor", default=DEFAULT_JSON_VALUE_ACCESSOR,
                          help="JSON path to extract the value from the object.")
        args.add_argument("--secret-path", help="The path to the secret.", required="secret_path" not in config_values)

        args.add_argument("--cmd", type=str, required="cmd" not in config_values)
        args.add_argument("--post-hooks", nargs='+', action='append', default=None)

        args.add_argument("-p", "--profile", default=DEFAULT_PROFILE_NAME)
        args.add_argument("-m", "--metrics-file")

        args.set_defaults(**config_values)

        # check if all config values in the file are actually recognized
        known_config_keys = [d.dest for d in args._actions]
        for conf_file_val in config_values:
            if conf_file_val not in known_config_keys:
                raise ValueError(f"Unknown config key: '{conf_file_val}', pick from '{known_config_keys}'")

        return args.parse_args(remaining_argv)


class Utils:
    @staticmethod
    def extract_json_value(data: Dict[str, Any], accessor: str):
        """ Access a dict using a jq-style path. """
        value = data
        for k in accessor.lstrip('.').split('.'):
            value = value[k]
        return value

    @staticmethod
    def build_auth_method(args: argparse.Namespace, http_pool: requests.Session = None) -> AuthMethod:
        if args.vault_role_id and (args.vault_secret_id or args.vault_secret_id_file):
            return AppRoleMethod.from_args(args, http_pool)

        if args.vault_token or args.vault_token_file:
            token = Utils.get_token(args)
            return StaticTokenMethod(args.vault_address, token, http_pool)

        raise ValueError("No auth method")

    @staticmethod
    def get_secret_id(args: argparse.Namespace) -> str:
        if args.vault_secret_id:
            return args.vault_secret_id

        p = Path(args.vault_secret_id_file).expanduser()
        if not p.exists():
            raise ValueError(f"File {p} does not exist")

        logging.info("Reading secret_id from file '%s'", p)
        return p.read_text(encoding="utf-8")

    @staticmethod
    def get_token(args: argparse.Namespace) -> str:
        if args.vault_token:
            return args.vault_token

        p = Path(args.vault_token_file).expanduser()
        if not p.exists():
            raise ValueError(f"File {p} does not exist")

        logging.info("Reading vault token from file '%s'", p)
        return p.read_text(encoding="utf-8")

    @staticmethod
    def write_metrics_file(metrics_file: str, success: bool, profile="default") -> None:
        # instead of adding another dependency, we just write this simple metrics file manually

        payload = f"""# TYPE occult_last_invocation_seconds gauge
occult_last_invocation_seconds{{profile="{ profile }"}} { datetime.datetime.now().timestamp() }
# TYPE occult_success_bool gauge
occult_success_bool{{profile="{ profile }"}} { 1 if success else 0 }
"""

        with open(metrics_file, 'w', encoding="utf-8") as metrics_file:
            metrics_file.write(payload)


class VaultException(Exception):
    pass


class CmdNotSuccessfulException(Exception):
    pass


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    try:
        args = ParsingUtils.parse_args()
    except ValueError as err:
        logging.error("Invalid config: %s", err)
        sys.exit(1)

    if args.quiet:
        logging.disable(logging.INFO)

    try:
        ParsingUtils.verify_args(args)
    except ValueError as err:
        logging.error("Invalid conf: %s", err)
        sys.exit(1)

    logging.info("Starting occult using profile '%s'", args.profile)

    http_pool = requests.Session()
    if args.backoff_attempts:
        retries = Retry(total=args.backoff_attempts, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        http_pool.mount("http://", HTTPAdapter(max_retries=retries))
        http_pool.mount("https://", HTTPAdapter(max_retries=retries))

    try:
        auth_method = Utils.build_auth_method(args, http_pool)
    except (FileNotFoundError, PermissionError) as err:
        logging.error("Could not authorize: %s", err)
        sys.exit(1)

    logging.info("Using '%s' auth method", auth_method.name)
    vault_client = VaultClient(args.vault_address, auth_method, http_pool=http_pool)

    drone = Drone(args.cmd, args.post_hooks)
    start_occult(args, vault_client, drone)


if __name__ == "__main__":
    main()
