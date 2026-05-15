# Snowflake CLI (`snow`) — Connect Manual

How to install the Snowflake CLI and configure a connection.

## 1. Install

```bash
brew install snowflake-cli
```

Verify:

```bash
snow --version
```

(Alternative: `pipx install snowflake-cli-labs` if not on macOS / Homebrew.)

## 2. Grab account identifier + username from the Snowflake UI

Log in to your Snowflake account in the browser. From the URL grab the account identifier:

```
https://<org>-<account>.snowflakecomputing.com
                ^^^^^^^^^^^^^^^^^
                account identifier  →  e.g. myorg-myacct
```

Also note:

- **Username** — top-right user menu → account name
- **Role** (optional) — e.g. `SYSADMIN`, `ANALYST`
- **Warehouse** (optional) — e.g. `COMPUTE_WH`
- **Database** / **Schema** (optional defaults)

## 3. Ask Claude to set up the SSO connection

Tell Claude:

> Add a Snowflake CLI connection named `dev` using SSO (`externalbrowser`). Account `<org>-<account>`, user `<username>`, role `<ROLE>`, warehouse `<WH>`, database `<DB>`. Then set it as default and test it.

Claude will run:

```bash
snow connection add \
  --connection-name dev \
  --account <org>-<account> \
  --user <username> \
  --role <ROLE> \
  --warehouse <WH> \
  --database <DB> \
  --authenticator externalbrowser

snow connection set-default dev
snow connection test -c dev
```

First `test` opens your browser to your IdP. Approve, return to terminal. Expect `Status: OK`.

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
