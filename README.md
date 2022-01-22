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
Occult tries to read a config file from `"$HOME/.occult.conf"`. You can override this behavior by setting the environment variable `OCCULT_CONFIG` or supplying the `-c` / `--config` flag.

The config file must not be world-readable.

### Example
A valid config example can be seen [here](contrib/test.json).

### Reference
| Key                  | Description                                                                                                                                      | Type         | Mandatory | Default    |
|----------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|--------------|-----------|------------|
| vault_address        | URL to the vault server                                                                                                                          | string       | Y         |            |
| vault_token          | Static token to access vault                                                                                                                     | string       | N*        |            |
| vault_token_file     | Flat file to read static vault token from                                                                                                        | string       | N*        |            |
| vault_role_id        | role_id for AppRole authentication against vault                                                                                                 | string       | N*        |            |
| vault_secret_id      | secret_id for AppRole authentication against vault                                                                                               | string       | N*        |            |
| vault_secret_id_file | Flat file to read secret_id from for AppRole authentication against vault                                                                        | string       | N*        |            |
| vault_ttl_increase   | Increase static vault token by x seconds. Specifying 0 or using AppRole authentication disablbes this feature                                    | int          | N         |            |
| quiet                | Only print warnings and errors                                                                                                                   | bool         | N         | False      |
| backoff_attempts     | Try n attempts before giving up                                                                                                                  | int          | N         | 5          |
| json_secret_path     | JQ-style accessor to extract the secret value from the JSON response object                                                                      | string       | Y         | data.value |
| secret_path          | Path to the secret to read from vault                                                                                                            | string       | Y         |            |
| cmd                  | Program (and arguments) to run after piping the secret                                                                                           | string array | Y         |            |
| post_hook            | Optional post hook command and arguments to run after successfully piping the secret                                                             | string array | N         |            |
| metrics_file         | File to write metrics to. You should point it to your [node_exporter textfile](https://github.com/prometheus/node_exporter#collectors) directory | string       | N         |            |
| profile              | Name of this profile. Makes it possible to have multiple configurations per host                                                                 | string       | N         | default    |

&ast; You have to *either* provide arguments for token authentication or AppRole authentication

## Metrics

| Name                           | Help                                        | Type  | Labels  |
|--------------------------------|---------------------------------------------|-------|---------|
| occult_token_expiry_seconds    | Unix timestamp when the used token expires  | Gauge | profile |
| occult_last_invocation_seconds | Unix timestamp when occult has been invoked | Gauge | profile |
| occult_success_bool            | Boolean whether this run was successful     | Gauge | profile |

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