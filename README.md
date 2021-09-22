# Occult
Reads a secret from Hashicorp Vault's K/V store and extracts & pipes the acquired secret to a pre-configured program.

## Demo
![demo](demo.gif)

## Configuration
Occult tries to read a config file from `"$HOME/.occult.conf"`. You can override this behavior by setting the environment variable `OCCULT_CONFIG`.

The config file must not be world-readable.

### Example
A valid config example can be seen [here](contrib/test.json).

### Values
| Key              | Description                                                                               | Type             | Mandatory |
|------------------|-------------------------------------------------------------------------------------------|------------------|-----------|
| vault_addr       | URL to the vault server                                                                   | string           | Y         |
| vault_path       | Path to read the secret from vault                                                        | string           | Y         |
| json_secret_path | JQ-style json path to extract the secret payload                                          | string           | N         |
| args             | Program to execute and pipe the secret to                                                 | string array     | Y         |
| post_hook        | Program (and arguments) to run after piping the secret                                    | string array     | N         |
| token            | Vault token to authenticate against vault                                                 | string           | N         |
| role_id          | Approle role id to acquire the vault token. Can not be used in conjunction with `token`   | string           | N         |
| secret_id        | Approle secret id to acquire the vault token. Can not be used in conjunction with `token` | string           | N         |
| metrics_file     | File to write metrics to                                                                  | string           | N         |