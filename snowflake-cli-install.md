# Snowflake CLI (`snow`) — Connect Manual

How to install the Snowflake CLI and configure a connection.

## Install

```bash
brew install snowflake-cli
# or
pipx install snowflake-cli-labs
```

Verify:

```bash
snow --version
```

## Add a connection

Interactive:

```bash
snow connection add
```

Prompts:

- **Connection name** — alias (e.g. `dev`)
- **Account** — `<orgname>-<accountname>` (from Snowflake URL: `https://<org>-<acct>.snowflakecomputing.com`)
- **User** — Snowflake username
- **Password** — skip if using SSO or key-pair
- **Role** — e.g. `SYSADMIN`
- **Warehouse** — e.g. `COMPUTE_WH`
- **Database** / **Schema** — optional defaults
- **Authenticator** — `snowflake` (password), `externalbrowser` (SSO), `SNOWFLAKE_JWT` (key-pair)

Non-interactive:

```bash
snow connection add \
  --connection-name dev \
  --account myorg-myacct \
  --user andrii \
  --role SYSADMIN \
  --warehouse COMPUTE_WH \
  --database ANALYTICS \
  --schema PUBLIC \
  --authenticator externalbrowser
```

## Config file

Stored at `~/.snowflake/config.toml`:

```toml
[connections.dev]
account = "myorg-myacct"
user = "andrii"
role = "SYSADMIN"
warehouse = "COMPUTE_WH"
database = "ANALYTICS"
schema = "PUBLIC"
authenticator = "externalbrowser"
```

Permissions must be `0600`:

```bash
chmod 0600 ~/.snowflake/config.toml
```

## Authentication methods

### SSO (browser)

```toml
authenticator = "externalbrowser"
```

Opens browser to your IdP on first use.

### Key-pair

Generate key:

```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out ~/.snowflake/rsa_key.p8 -nocrypt
openssl rsa -in ~/.snowflake/rsa_key.p8 -pubout -out ~/.snowflake/rsa_key.pub
```

Register public key in Snowflake:

```sql
ALTER USER andrii SET RSA_PUBLIC_KEY='<paste pubkey body, no BEGIN/END lines>';
```

Config:

```toml
authenticator = "SNOWFLAKE_JWT"
private_key_path = "/Users/andriik-mbp/.snowflake/rsa_key.p8"
```

### Password

```toml
authenticator = "snowflake"
password = "..."   # or use env var SNOWFLAKE_PASSWORD
```

## Set default and test

```bash
snow connection set-default dev
snow connection test -c dev
```

Expected output:

```
Status: OK
```

## Use the connection

```bash
snow sql -q "SELECT CURRENT_USER(), CURRENT_ROLE();"
snow sql -c dev -f script.sql
snow connection list
```

## Troubleshooting

- `250001 (08001)` — bad account locator. Use `org-acct`, not the full URL.
- SSO login loops — clear `~/.snowflake/` token cache.
- JWT error `390144` — public key not registered or fingerprint mismatch. Compare with:

  ```sql
  DESC USER andrii;
  ```

  Look at `RSA_PUBLIC_KEY_FP`.
