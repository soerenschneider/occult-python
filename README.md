# Occult
Reads a secret from Hashicorp Vault's K/V store, extracts & pipes the acquired secret to a pre-configured program in order to automate a process involving a secret.

## Demo
![demo](demo.gif)

## Configuration
Occult tries to read a config file from `"$HOME/.occult.conf"`. You can override this behavior by setting the environment variable `OCCULT_CONFIG`.

The config file must not be world-readable.

### Example
A valid config example can be seen [here](contrib/test.json).

### Reference
| Key              | Description                                                                               | Type             | Mandatory | Default    |
|------------------|-------------------------------------------------------------------------------------------|------------------|-----------|------------|
| vault_addr       | URL to the vault server                                                                   | string           | Y         |            |
| vault_path       | Path to read the secret from vault                                                        | string           | Y         |            |
| json_secret_path | JQ-style json path to extract the secret payload                                          | string           | N         | data.value |
| args             | Program to execute and pipe the secret to                                                 | string array     | Y         |            |
| post_hook        | Program (and arguments) to run after piping the secret                                    | string array     | N         |            |
| token            | Vault token to authenticate against vault                                                 | string           | N*        |            |
| role_id          | Approle role id to acquire the vault token.                                               | string           | N*        |            |
| secret_id        | Approle secret id to acquire the vault token.                                             | string           | N*        |            |
| metrics_file     | File to write metrics to                                                                  | string           | N         |            |

&ast; You have to either provide a _token_ or a _role_id_ / _secret_id_ tuple

## Vault Configuration
A working example can be found [here](https://github.com/soerenschneider/tf-vault)
