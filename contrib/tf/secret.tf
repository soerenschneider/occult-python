resource "vault_generic_secret" "occult" {
  path = "secret/occult/test"

  data_json = <<EOT
{
  "hello":   "world"
}
EOT
}
