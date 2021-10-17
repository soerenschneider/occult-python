# Occult
Reads a secret from Hashicorp Vault's K/V store, extracts & pipes the acquired secret to a pre-configured program in order to automate a process involving a secret.

## Demo
![demo](demo.gif)

## Installation

```shell
git clone https://github.com/soerenschneider/occult.git
sudo make -C occult install
```

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
| metrics_file     | File to write metrics to. You should point it to your [node_exporter textfile](https://github.com/prometheus/node_exporter#collectors) directory                                                                  | string           | N         |            |
| profile          | Name of this profile. Makes it possible to have multiple configurations per host          | string           | N         | default    |

&ast; You have to *either* provide token or tuple of role_id / secret_id

## Vault Example Configuration

Terraform snippet to configure Vault accordingly

```hcl
resource "vault_policy" "occult" {
  name = "occult_${var.secret_name}"

  policy = <<EOT
path "secret/data/occult/${var.secret_name}" {
  capabilities = ["read"]
}
EOT
}

resource "vault_token_auth_backend_role" "occult" {
  role_name = vault_policy.occult.name
  allowed_policies = [
    vault_policy.occult.name,
    "default"
  ]
  orphan = true
  token_bound_cidrs = var.token_cidrs
}

resource "vault_token" "occult" {
  depends_on = [vault_token_auth_backend_role.occult]
  role_name  = vault_policy.occult.name
  policies = [
    vault_policy.occult.name
  ]
  display_name = "occult-${var.secret_name}"
  renewable    = true
  ttl          = var.token_ttl
}
```

A complete, fully functional example can be found [here](https://github.com/soerenschneider/tf-vault)