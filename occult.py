#!/usr/bin/env python3

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


class Context:
    def __init__(self, config):
        self._endpoint = config["addr"]
        if "role_id" in config and "secret_id" in config:
            self._role_id = config["role_id"]
            self._secret_id = config["secret_id"]
        self._args = config["args"]

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
            raise Exception(f"Couldn't login, got HTTP {resp.status_code}: {resp.content}")

        content = json.loads(resp.content)
        return content["auth.client_token"]

    @staticmethod
    def _dynamic_access_json(data: Dict[str, str], key: str):
        value = data
        for k in key.split('.'):
            value = value[k]
        return value

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
        proc = Popen(self._args, stdin=PIPE)
        proc.communicate(input=enc)
        if proc.returncode != 0:
            raise CmdNotSuccessfulException()

    def post_hook(self) -> None:
        logging.info("Running post hook cmd '%s'", self._post_hook[0])
        proc = Popen(self._post_hook)
        if proc.returncode != 0:
            raise CmdNotSuccessfulException()


def load_config(location: str):
    logging.info("Trying to read config from '%s'", location)
    with open(location, 'r') as config_file:
        data = config_file.read()
        return json.loads(data)


def validate_config(config):
    if not config:
        raise Exception("no config supplied")

    keywords = ["addr", "path", "args"]
    for keyword in keywords:
        if keyword not in config:
            raise ConfigError(f"no '{keyword}' configured")

    if "token" not in config:
        if "role_id" not in config and "secret_id" not in config:
            raise ConfigError(f"either specify 'token' or 'secret_id' and 'role_id' values")


def main(config_file: str) -> None:
    logging.basicConfig(format='%(asctime)s %(message)s')
    logging.getLogger().setLevel(logging.INFO)

    conf = None
    try:
        conf = load_config(config_file)
        validate_config(conf)
        logging.info("Config successfully read and validated")
    except FileNotFoundError as err:
        logging.error("No config file found, quitting: %s", err)
        sys.exit(1)
    except ConfigError as err:
        logging.error("Invalid config: %s", err)
        sys.exit(1)

    try:
        ctx = Context(conf)
        token = None
        if "token" in conf:
            token = conf["token"]
        else:
            token = ctx.authenticate()

        json_secret_path = DEFAULT_JSON_SECRET_PATH
        if "json_secret_path" in conf:
            json_secret_path = conf["json_secret_path"]
        password = ctx.read_pass(conf["path"], token, json_secret_path)
        ctx.send_password(password)
        if "post_hook" in conf and len(conf["post_hook"]) > 0:
            ctx.post_hook()
    except KeyError as err:
        logging.error("No such field found in reply from vault, check json_secret_path: %s", err)
        sys.exit(1)
    except VaultException as err:
        logging.error("Error talking to vault: %s", err)
        sys.exit(1)
    except FileNotFoundError as err:
        logging.error("No such cmd: %s", err)
        sys.exit(1)
    except CmdNotSuccessfulException:
        logging.error("Command unsuccessful")
        sys.exit(1)


class ConfigError(Exception):
    pass


class VaultException(Exception):
    pass


class CmdNotSuccessfulException(Exception):
    pass


if __name__ == "__main__":
    configFile = os.getenv("OCCULT_CONFIG", DEFAULT_CONFIG_LOCATION)
    main(configFile)
