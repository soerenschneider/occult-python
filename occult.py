#!/usr/bin/env python3
import datetime
import os
import logging
import json
import sys

from urllib.parse import urljoin
from subprocess import Popen, PIPE
from typing import Optional, Dict

import backoff
import requests

DEFAULT_CONFIG_LOCATION = os.path.expanduser("~/.occult.conf")
DEFAULT_JSON_SECRET_PATH = "data.value"
ENV_OCCULT_CONFIG = "OCCULT_CONFIG"


class Context:
    def __init__(self, config):
        self._endpoint = config["addr"]
        if "role_id" in config and "secret_id" in config:
            self._role_id = config["role_id"]
            self._secret_id = config["secret_id"]
        self._args = config["args"]

        if "post_hook" in config:
            self._post_hook = config["post_hook"]
        else:
            self._post_hook = []

    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException)
    def authenticate(self) -> Optional[str]:
        logging.info("Trying to authenticate with app role '%s'", self._role_id)
        url = urljoin(self._endpoint, "/auth/approle/login")
        data = {
            "role_id": self._role_id,
            "secret_id": self._secret_id
        }
        resp = requests.post(data=data, url=url)
        if resp.status_code > 204:
            raise VaultException(f"Couldn't login, got HTTP {resp.status_code}: {resp.content}")

        content = json.loads(resp.content)
        return content["auth.client_token"]

    @staticmethod
    def _dynamic_access_json(data: Dict[str, str], key: str):
        value = data
        for k in key.split('.'):
            value = value[k]
        return value

    def get_token_ttl(self, token: Dict) -> Optional[int]:
        content = self._lookup_self(token)
        if "ttl" in content["data"]:
            return content["data"]["ttl"]
        return None

    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException)
    def _lookup_self(self, token: str) -> Dict:
        logging.info("Trying to lookup used token")
        url = urljoin(self._endpoint, "/v1/auth/token/lookup-self")
        resp = requests.get(headers={'X-Vault-Token': token}, url=url)
        if resp.status_code > 204:
            raise VaultException(f"Couldn't lookup token, got HTTP {resp.status_code}: {resp.content} for {url}")

        return json.loads(resp.content)

    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException)
    def read_pass(self, vault_secret_path: str, token: str, json_secret_path: str) -> Optional[str]:
        logging.info("Trying to read secret '%s'", vault_secret_path)
        url = urljoin(self._endpoint, f"/v1/secret/data/{vault_secret_path}")
        resp = requests.get(headers={'X-Vault-Token': token}, url=url)
        if resp.status_code > 204:
            raise VaultException(f"Couldn't fetch secret, got HTTP {resp.status_code}: {resp.content} for {url}")

        content = json.loads(resp.content)
        return Context._dynamic_access_json(content, json_secret_path)

    def send_password(self, password: str) -> None:
        logging.info("Sending password to defined command '%s'", self._args[0])
        enc = password.encode('utf-8')
        with Popen(self._args, stdin=PIPE) as proc:
            proc.communicate(input=enc)
            if proc.returncode != 0:
                raise CmdNotSuccessfulException()

    def post_hook(self) -> None:
        if not self._post_hook:
            return

        logging.info("Running post hook cmd '%s'", self._post_hook[0])
        with Popen(self._post_hook) as proc:
            if proc.returncode != 0:
                raise CmdNotSuccessfulException()


def load_config(location: str):
    logging.info("Trying to read config from '%s'", location)
    with open(location, 'r', encoding="utf-8") as config_file:
        data = config_file.read()
        return json.loads(data)


def validate_config(config):
    if not config:
        raise Exception("no config supplied")

    keywords = ["addr", "vault_path", "args"]
    for keyword in keywords:
        if keyword not in config:
            raise ConfigError(f"no '{keyword}' configured")

    if "token" not in config:
        if "role_id" not in config and "secret_id" not in config:
            raise ConfigError("either specify 'token' or 'secret_id' and 'role_id' values")


def write_metrics_file(metrics_file: str, token_ttl: int, success: bool) -> None:
    # instead of adding another dependency, we just write this simple metrics file manually
    payload = f"""# TYPE occult_token_ttl_seconds gauge
occult_token_ttl_seconds { token_ttl }
# TYPE occult_last_invocation_seconds gauge
occult_last_invocation_seconds { datetime.datetime.now().timestamp() }
# TYPE occult_success_bool gauge
occult_success_bool { 1 if success else 0 }"""

    with open(metrics_file, 'w', encoding="utf-8") as f:
        f.write(payload)


def _read_config(config_file: str) -> Dict:
    conf = load_config(config_file)
    validate_config(conf)
    logging.info("Config successfully read and validated")
    return conf


def main(conf: Dict) -> None:
    success = False
    ttl = -1
    try:
        ctx = Context(conf)
        token = None
        if "token" in conf:
            token = conf["token"]
        else:
            token = ctx.authenticate()

        ttl = ctx.get_token_ttl(token)
        logging.info("Token expires in %d seconds (on %s)", ttl, datetime.datetime.now() + datetime.timedelta(seconds=ttl))

        json_secret_path = DEFAULT_JSON_SECRET_PATH
        if "json_secret_path" in conf:
            json_secret_path = conf["json_secret_path"]
        password = ctx.read_pass(conf["vault_path"], token, json_secret_path)

        ctx.send_password(password)
        ctx.post_hook()

        success = True
    except KeyError as err:
        logging.error("No such field found in reply from vault, check json_secret_path: %s", err)
    except VaultException as err:
        logging.error("Error talking to vault: %s", err)
    except FileNotFoundError as err:
        logging.error("No such cmd: %s", err)
    except CmdNotSuccessfulException:
        logging.error("Command unsuccessful")

    if "metrics_file" in conf:
        logging.info("Writing metrics to %s", conf["metrics_file"])
        write_metrics_file(conf["metrics_file"], ttl, success)
    else:
        logging.warning("Not writing metrics, no metrics_file specified")

    if not success:
        sys.exit(1)


class ConfigError(Exception):
    pass


class VaultException(Exception):
    pass


class CmdNotSuccessfulException(Exception):
    pass


if __name__ == "__main__":
    config_file = os.getenv(ENV_OCCULT_CONFIG, DEFAULT_CONFIG_LOCATION)
    logging.basicConfig(format='%(asctime)s %(message)s')
    logging.getLogger().setLevel(logging.INFO)

    conf = None
    try:
        conf = _read_config(config_file)
    except FileNotFoundError as err:
        logging.error("No config file found, quitting: %s", err)
        sys.exit(1)
    except ConfigError as err:
        logging.error("Invalid config: %s", err)
        sys.exit(1)

    main(conf)
