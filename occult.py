#!/usr/bin/env python3
import datetime
import os
import logging
import json
import sys
import stat

from urllib.parse import urljoin
from subprocess import Popen, PIPE, DEVNULL
from typing import Optional, Dict, Any

import backoff
import requests

CONF_METRICS_FILE = "metrics_file"
CONF_JSON_SECRET_PATH = "json_secret_path"
CONF_SECRET_ID = "secret_id"
CONF_ROLE_ID = "role_id"
CONF_TOKEN = "token"
CONF_POST_HOOK = "post_hook"
CONF_ARGS = "args"
CONF_VAULT_PATH = "vault_path"
CONF_VAULT_ROLE_ID = "role_id"
CONF_VAULT_SECRET_ID = "secret_id"
CONF_VAULT_ADDR = "vault_addr"
CONF_PROFILE = "profile"

DEFAULT_PROFILE_NAME = "default"
DEFAULT_CONFIG_LOCATION = os.path.expanduser("~/.occult.conf")
DEFAULT_JSON_SECRET_PATH = "data.value"
ENV_OCCULT_CONFIG = "OCCULT_CONFIG"


class Context:
    def __init__(self, config):
        self._endpoint = config[CONF_VAULT_ADDR]
        if CONF_VAULT_ROLE_ID in config and CONF_VAULT_SECRET_ID in config:
            self._role_id = config[CONF_VAULT_ROLE_ID]
            self._secret_id = config[CONF_VAULT_SECRET_ID]
        self._args = config[CONF_ARGS]

        if CONF_POST_HOOK in config:
            self._post_hook = config[CONF_POST_HOOK]
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
    def _lookup_self(self, token: str) -> Dict[str, Any]:
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
        with Popen(self._args, stdin=PIPE, stdout=DEVNULL) as proc:
            proc.communicate(input=enc)
            proc.wait(60)
            if proc.returncode != 0:
                raise CmdNotSuccessfulException()

    def post_hook(self) -> None:
        if not self._post_hook:
            return

        logging.info("Running post hook cmd '%s'", self._post_hook[0])
        with Popen(self._post_hook, stdout=DEVNULL) as proc:
            proc.wait(15)
            if proc.returncode != 0:
                raise CmdNotSuccessfulException()


def load_config(location: str) -> Dict[str, Any]:
    logging.info("Trying to read config from '%s'", location)
    with open(location, 'r', encoding="utf-8") as config_file:
        data = config_file.read()
        return json.loads(data)


def validate_config(config: Dict[str, Any]) -> None:
    if not config:
        raise Exception("no config supplied")

    keywords = [CONF_VAULT_ADDR, CONF_VAULT_PATH, CONF_ARGS]
    for keyword in keywords:
        if keyword not in config:
            raise ConfigError(f"no '{keyword}' configured")

    if CONF_TOKEN not in config:
        if CONF_ROLE_ID not in config and CONF_SECRET_ID not in config:
            raise ConfigError(f"either specify '{CONF_TOKEN}' or both '{CONF_SECRET_ID}' and '{CONF_ROLE_ID}' values")


def write_metrics_file(metrics_file: str, token_ttl: int, success: bool, profile="default") -> None:
    # instead of adding another dependency, we just write this simple metrics file manually
    expiry = datetime.datetime.now() + datetime.timedelta(seconds=token_ttl)
    payload = f"""# TYPE occult_token_ttl_seconds gauge
occult_token_expiry_seconds{{profile="{ profile }"}} { expiry.timestamp() }
# TYPE occult_last_invocation_seconds gauge
occult_last_invocation_seconds{{profile="{ profile }"}} { datetime.datetime.now().timestamp() }
# TYPE occult_success_bool gauge
occult_success_bool{{profile="{ profile }"}} { 1 if success else 0 }
"""

    with open(metrics_file, 'w', encoding="utf-8") as metrics_file:
        metrics_file.write(payload)


def _read_config(config_file: str) -> Dict[str, Any]:
    conf = load_config(config_file)
    validate_config(conf)
    logging.info("Config successfully read and validated")
    return conf


def _check_config_permissions(config_file: str) -> None:
    file_stat = os.stat(config_file)
    grp_readable = bool(file_stat.st_mode & stat.S_IRGRP)
    world_readable = bool(file_stat.st_mode & stat.S_IRWXG)
    if grp_readable or world_readable:
        raise ConfigError("Config file must not be group/world readable")


def start(conf: Dict) -> None:
    success = False
    ttl = -1
    try:
        profile = "default"
        if CONF_PROFILE in conf:
            profile = conf[CONF_PROFILE]
            logging.info("Started occult using profile %s", profile)

        ctx = Context(conf)
        if "token" in conf:
            token = conf["token"]
        else:
            token = ctx.authenticate()

        ttl = ctx.get_token_ttl(token)
        if ttl == 0:
            logging.info("Used token does not expire")
        else:
            logging.info("Token expires in %d seconds (on %s)", ttl, datetime.datetime.now() + datetime.timedelta(seconds=ttl))

        json_secret_path = DEFAULT_JSON_SECRET_PATH
        if CONF_JSON_SECRET_PATH in conf:
            json_secret_path = conf[CONF_JSON_SECRET_PATH]
        password = ctx.read_pass(conf[CONF_VAULT_PATH], token, json_secret_path)

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

    if CONF_METRICS_FILE in conf:
        logging.info("Writing metrics to %s", conf[CONF_METRICS_FILE])
        write_metrics_file(conf[CONF_METRICS_FILE], ttl, success, profile)
    else:
        logging.warning(f"Not writing metrics, no {CONF_METRICS_FILE} specified")

    if not success:
        sys.exit(1)


class ConfigError(Exception):
    pass


class VaultException(Exception):
    pass


class CmdNotSuccessfulException(Exception):
    pass


def main():
    logging.basicConfig(format='%(asctime)s %(message)s')
    logging.getLogger().setLevel(logging.INFO)
    config_file = os.getenv(ENV_OCCULT_CONFIG, DEFAULT_CONFIG_LOCATION)

    try:
        _check_config_permissions(config_file)
        conf = _read_config(config_file)
    except FileNotFoundError as err:
        logging.error("No config file found, quitting: %s", err)
        sys.exit(1)
    except ConfigError as err:
        logging.error("Invalid config: %s", err)
        sys.exit(1)

    start(conf)


if __name__ == "__main__":
    main()
