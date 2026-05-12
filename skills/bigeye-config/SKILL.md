---
name: bigeye-config
description: Use when the user wants to configure the BigEye plugin's scope (workspace + filters), run the first-run wizard, manage named profiles, or verify CLI/MCP setup. Also auto-invoked by other BigEye skills when the config file is missing.
user-invocable: true
---

# BigEye Configuration

Owns the per-user profiles file at `~/.claude/bigeye-plugin/profiles.json` AND the matching workspace sections of `~/.bigeye/config.ini`. This is the **only** skill that writes to either file.

**Before doing anything else**, follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection. Output shape lives in `skills/bigeye/references/output.md`.

## Arguments

Parse `$ARGUMENTS` (space-separated). First token is the subcommand; anything after is arguments to that subcommand.

| Invocation | Behavior |
|---|---|
| (empty) or `show` | Print active profile name + all profiles in a table |
| `init` | Run wizard, write a profile, set as default. If a file already exists, ask whether to overwrite or add |
| `add <name>` | Run wizard, add a new profile without changing the default |
| `switch <name>` | Set `default_profile` to `<name>` |
| `edit <name>` | Re-run wizard against an existing profile |
| `delete <name>` | Remove a profile. Refuse if it is the default and no alternative exists |
| `settings show` | Print the merged effective settings (file values + shipped defaults for any missing keys) |
| `settings edit <key> <value>` | Overwrite a single dotted-path key in `~/.claude/bigeye-plugin/settings.json` |
| `verify` / `verify <name>` | Run a four-point health check (CLI install, CLI workspace, CLI auth, MCP reachability) and print a status table |
| `hints add` | Author a custom hint via NL → compile → confirm → save (uses `references/hints.md`) |
| `hints list [<profile>]` | List custom hints for the given (or active) profile |
| `hints edit <index>` | Edit hint at index (re-runs compile prompt with prior raw pre-filled) |
| `hints delete <index>` | Remove hint at index |
| `virtual-tables add <name>` | MCP-resolve a virtual table by name → save `{id, name}` to active profile |
| `virtual-tables list` | List virtual tables on the active profile |
| `virtual-tables delete <name-or-id>` | Remove a virtual table from the active profile |
| `snow show` | Print active profile's `snow` block + the connection it maps to in `~/.snowflake/config.toml` |
| `snow set <profile>` | Set `snow.profile` on active profile. Verify the connection exists. Run `snow connection test -c <profile>` |
| `snow set <profile> --warehouse <w>` | Same + set `default_warehouse` |
| `snow set <profile> --role <r>` | Same + set `default_role` |
| `snow unset` | Remove `snow` block from active profile |
| `snow verify` | Run `snow connection test` + canary `SELECT 1` + parse `SHOW GRANTS` for write privileges. Print PASS/FAIL per check |

## Config Files

**`~/.claude/bigeye-plugin/profiles.json`** — plugin-owned; contains profile definitions + default pointer.

**Schema (v0.5):**

```json
{
  "active_profile": "prod",
  "profiles": {
    "prod": {
      "workspace_id": 42,
      "scope": {
        "data_sources":   [{"id": 17, "name": "warehouse_prod"}],
        "schemas":        [],
        "tables":         [{"id": 901, "name": "orders_main"}],
        "virtual_tables": []
      },
      "monitored_rules": [{"id": 1, "name": "freshness"}],
      "custom_hints": [],
      "snow": {
        "profile": "ro-analytics",
        "default_warehouse": "ANALYTICS_RO_WH",
        "default_role": "DATA_READER"
      }
    }
  }
}
```

`active_profile` (formerly `default_profile`) keeps backward-compatible read; new writes use `active_profile`.

The `snow` block is optional. Required by `/bigeye-investigate`; missing → /bigeye-investigate prints "No Snowflake profile configured. Run /bigeye-config snow set <profile>." and stops.

The plugin no longer requires the BigEye CLI for the v0.5 user-facing pillars. The CLI section in `~/.bigeye/config.ini` is **only** written when the user opts into legacy CLI integration (kept for hidden skills). When the wizard finishes, ask: `Also configure ~/.bigeye/config.ini for legacy CLI use? (y/n, default n)`. Default `n` skips the file write entirely.

**`~/.bigeye/credentials`** — user-owned, never touched by the plugin.

**Field rules:**
- `default_profile` must reference a key in `profiles`.
- Each profile requires `workspace_id`. All other fields are optional arrays.
- Missing filter fields default to empty arrays when written.
- `tags` is removed — see migration below.

## Settings File

`~/.claude/bigeye-plugin/settings.json` — plugin-owned; user-editable via the `settings show` / `settings edit` subcommands. Schema (defaults shown):

```json
{
  "_meta": { "version": "0.5.0", "upgrade_seen": false },
  "slack": { "channel": "#data-quality-alerts", "mention_group": "@data-oncall", "critical_only": true },
  "severity": { "critical_ack_hours": 4, "critical_related_count": 3, "warning_ack_hours": 24 },
  "triage": { "max_issues": 50, "default_brief_rows": 10 },
  "deploy": { "default_lookback_days": 7, "tag": "deployed-by-plugin" },
  "view": { "default_view": "brief" },
  "docs": { "base_url": "https://docs.bigeye.com" },
  "roster": { "batch_size": 5, "max_facts_per_issue": 6 }
}
```

`settings.json` is seeded by `preamble.md` Step 2 on first encounter. This skill is the only one that **edits** the file directly.

## Custom Hints

Hint compile + storage are documented in `skills/bigeye/references/hints.md`. This skill is the only writer for `custom_hints`.

### Subcommand: `hints add`

1. Hard-fail if `MCP_AVAILABLE=false` (per preamble Step 7.E).
2. Ask: `Hint scope? (table / monitor)`.
3. Ask for the target name. Resolve via MCP (`mcp__bigeye__list_tables` for tables; `mcp__bigeye__list_table_metrics` for monitors). On ambiguity → list candidates with IDs, user picks.
4. Ask: `Describe the hint in plain text.`
5. Run the compile prompt from `references/hints.md`. If ambiguous → ask follow-up. Refuse to save without a compiled shape.
6. Show the compiled JSON. Ask: `Save this hint? (y/n)`.
7. On `y`: append `{scope, target_id, target_name, raw, compiled, created_at: now()}` to `profiles[<active>].custom_hints` and write atomically.
8. On `n`: discard, ask `Try again? (y/n)`. On `y` → restart at Step 4. On `n` → exit.

### Subcommand: `hints list [<profile>]`

Print a numbered table:

```
# | Scope   | Target            | Type             | Raw
1 | table   | orders            | noise_threshold  | ignore deltas under 2% on row_count
2 | monitor | metric#4421       | expected_pattern | weekend spikes are expected
```

If the profile has no hints → `No custom hints on profile {name}. Add via /bigeye-config hints add.`

### Subcommand: `hints edit <index>`

1. Load profile. Validate index is in range.
2. Show the existing compiled form.
3. Re-run `hints add` flow with the existing `raw` pre-filled (user can edit before compile).
4. Replace at the same index. Write atomically.

### Subcommand: `hints delete <index>`

1. Load profile, validate index.
2. Confirm: `Delete hint #{index}: {raw}? (y/n)`.
3. On `y` → splice out, write atomically.

## Virtual Tables

### Subcommand: `virtual-tables add <name>`

1. Hard-fail if `MCP_AVAILABLE=false`.
2. Search via `mcp__bigeye__search_lineage_nodes` (or equivalent) filtered to virtual tables in the workspace. On ambiguity → list candidates with IDs, user picks.
3. If `name` matches a regular table only → reject with: `` `{name}` is a regular table, not a virtual table. Add it via the wizard's table step instead. ``
4. Append `{id, name}` to `scope.virtual_tables`. Write atomically.

### Subcommand: `virtual-tables list`

Print:

```
# | ID  | Name
1 | 55  | active_users_30d
```

### Subcommand: `virtual-tables delete <name-or-id>`

1. Resolve to one entry. Ambiguity → ask which.
2. Splice out. Write atomically.

## Profile-Name Validation

Profile names MUST match `^[a-zA-Z0-9_-]+$`. Reject anything else at the wizard's first step. The name `DEFAULT` is rejected unless the user explicitly confirms they want to overwrite the CLI's default section.

## Tag Migration

On every read of `profiles.json`:
1. If any profile contains a non-empty `tags` field, strip it in-memory before use.
2. Print once per session:
   ```
   Note: `tags` filter removed in this plugin release.
   Stripping from profile `<name>` on read. Run `/bigeye-config edit <name>` to rewrite cleanly.
   ```
3. Do not modify the on-disk file until the wizard writes it next.

## Procedure

### Subcommand: `show` (or no argument)

1. Read `~/.claude/bigeye-plugin/profiles.json`. If missing:
   ```
   No BigEye profiles configured yet.
   Run `/bigeye-config init` to set one up.
   ```
   Stop.
2. Parse the JSON; apply tag migration.
3. Print:
   ```
   ## BigEye Profiles

   Active (default): **{default_profile}**

   | Profile | Workspace | Sources | Tables | Schemas |
   |---------|-----------|---------|--------|---------|
   | {name} | {workspace_id} | {count} | {count} | {count} |
   ```

### Subcommand: `init`

1. Read `~/.claude/bigeye-plugin/profiles.json`. If it exists, ask:
   ```
   A config file already exists. What would you like to do?
   1. Overwrite with a new default profile
   2. Add a new profile alongside the existing ones
   3. Cancel
   ```
2. If it does not exist, ask: *"What would you like to name this profile? (default: `work-area`)"*. Validate per Profile-Name Validation rules.
3. Run the **Wizard Flow** below.
4. Ensure directories exist:
   ```bash
   mkdir -p ~/.claude/bigeye-plugin
   mkdir -p ~/.bigeye
   ```
5. Write `~/.claude/bigeye-plugin/profiles.json` with the final content.
6. Read the wizard's opt-in answer (from Wizard Flow Step 8 above; it's now part of the summary block per Task 6.6 demotion).

   - **If the user answered `n` (default):** skip the `config.ini` write entirely. Skip Step 7 (CLI verify). Go to Step 8.
   - **If the user answered `y`:** add/replace the `[<profile>]` section in `~/.bigeye/config.ini` with `workspace_id = <id>` (leave all other sections untouched). If `~/.bigeye/config.ini` doesn't exist, create it with only the new section (no implicit `[DEFAULT]`).

7. **Only when opt-in answer is `y`:** verify CLI binding:
   ```bash
   bigeye -w <profile> configure list
   ```
   On non-zero exit, print the CLI error and a note:
   *"CLI workspace configured, but `bigeye configure list` failed. You likely need to set up `~/.bigeye/credentials` via `bigeye configure` or by following `bigeye-cli-install.md`."*

8. Print the success message — opt-in branch determines which paths are listed:

   ```
   Wrote profile `{name}` to:
     ~/.claude/bigeye-plugin/profiles.json (set as default)
     {if opt-in == y:}  ~/.bigeye/config.ini (section [{name}], workspace_id={id})

   Try `/bigeye-config verify` to confirm setup, then `/bigeye-roster` to walk today's issues.
   ```

### Subcommand: `add <name>`

1. Validate `<name>` per Profile-Name Validation rules.
2. Read existing `profiles.json`. If missing, tell the user to run `/bigeye-config init` first.
3. **Only when the wizard's opt-in answer is `y`:** if `[<name>]` already exists in `~/.bigeye/config.ini`, print current contents and ask:
   *"A CLI section `[<name>]` already exists with workspace_id=<X>. Overwrite with the new profile's workspace_id? (y/n/pick-different-name)"*. If opt-in is `n`, skip this step.
4. Run the Wizard Flow.
5. Merge new profile into `profiles`. Do not change `default_profile`.
6. **Only when opt-in answer is `y`:** add/replace `[<name>]` in `~/.bigeye/config.ini`.
7. Print confirmation.

### Subcommand: `switch <name>`

1. Read `profiles.json`. If missing, tell the user to run `/bigeye-config init`.
2. If `<name>` not in `profiles`, print available and stop.
3. Update `default_profile` to `<name>`; write file.
4. Print: `Switched default profile to \`{name}\`.`

### Subcommand: `edit <name>`

1. Read file. If missing or `<name>` not in `profiles`, error.
2. Show current values. Apply tag migration.
3. Run Wizard Flow with current values pre-filled (let user press enter to keep each).
4. Replace the profile. Do not change `default_profile`.
5. Write `profiles.json`. **Only when the wizard's opt-in answer is `y`:** update `[<name>]` in `~/.bigeye/config.ini` with the new `workspace_id`.
6. Print confirmation.

### Subcommand: `delete <name>`

1. Read file. If missing or `<name>` not in `profiles`, error.
2. If `<name>` is the `default_profile`:
   - If only one profile exists: refuse. Print the standard error and stop.
   - Otherwise: ask which profile to promote as the new default.
3. Ask confirmation: *"Also remove `[<name>]` from `~/.bigeye/config.ini`? (y/n) — Other tools on this machine may be using this section."*
4. Remove profile from `profiles.json`. If user confirmed, remove the section from `config.ini`.
5. Write file(s). Print confirmation listing exactly what was removed.

### Subcommand: `settings show`

1. `Read` `~/.claude/bigeye-plugin/settings.json`. If missing, follow `preamble.md` Step 2 to seed defaults, then re-read.
2. Print:
   ```
   ## BigEye Plugin Settings

   ~/.claude/bigeye-plugin/settings.json

   {pretty-printed JSON, 2-space indent, keys in canonical order: _meta, slack, severity, triage, deploy, view, docs, roster}
   ```
3. Below the JSON, print this fixed line:
   ```
   Edit any key with: /bigeye-config settings edit <dotted.key> <value>
   ```

### Subcommand: `settings edit <key> <value>`

1. If `<key>` is `_meta.upgrade_seen`, refuse with:
   ```
   Error: _meta.upgrade_seen is managed by the plugin.
   Fix:   (no action needed)
   Why:   This flag flips automatically on first run after upgrade.
   ```
   Stop. Otherwise continue.
2. Validate `<key>` matches `^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)+$` (dotted path, at least 2 segments). Reject otherwise:
   ```
   Error: invalid settings key '<key>'.
   Fix:   /bigeye-config settings show     (lists valid keys)
   Why:   Keys must be dotted paths (e.g., slack.channel, view.default_view).
   ```
3. `Read` settings.json (seed via preamble Step 2 if missing).
4. Walk the dotted path; if any intermediate key is missing, refuse with:
   ```
   Error: parent path '<prefix>' does not exist in settings.json.
   Fix:   /bigeye-config settings show     (verify the structure)
   Why:   This skill never creates new top-level groups — only edits known leaf keys.
   ```
5. Type-coerce `<value>`:
   - If the existing value is `true`/`false`, parse `<value>` as boolean (`true`/`false` literal — case insensitive). Anything else → reject.
   - If the existing value is a number, parse `<value>` as integer (or float if the existing was a float). Reject on parse failure.
   - Otherwise treat as string. Strip surrounding quotes if present.
6. Replace the value in memory. Update `_meta.version` to `"0.4.0"` if absent.
7. Write atomically: write `settings.json.tmp` in the same directory, then rename.
8. Print:
   ```
   Updated <key>: <old> -> <new>
   Wrote ~/.claude/bigeye-plugin/settings.json.
   ```

### Subcommand: `verify` / `verify <name>`

Resolve the profile name (argument or active default). Print:

```
BigEye Plugin — Setup Status

[{a}] CLI installed            {bigeye --version output or "not on PATH"}
[{b}] CLI workspace configured [{profile}] → workspace_id={id} (~/.bigeye/config.ini)
[{c}] CLI auth                 {~/.bigeye/credentials status}
[{d}] MCP server reachable     {MCP probe result}
                              {when reachable: feature list enabled by MCP}
[{e}] Settings file               {settings.json: present / missing}

Overall: {ready / partially degraded / setup required}
```

Status markers use plain ASCII: `[✓]` (good), `[!]` (warn), `[✗]` (fail), `[~]` (info).

Check steps:
- **a**: run `which bigeye`. If non-zero, mark `[✗]` and suggest `bigeye-cli-install.md`.
- **b**: read the resolved profile's `workspace_id`, confirm `[<profile>]` exists in `~/.bigeye/config.ini` with that value. Mismatch → `[!]`.
- **c**: `test -r ~/.bigeye/credentials`. Absent → `[!]`, point at `bigeye configure`.
- **d**: call `mcp__bigeye__list_data_sources` with `workspace_id`. On success, list the features MCP unlocks. On failure, mark `[!]` and point at `bigeye-mcp-install.md`.
- **e**: `test -r ~/.claude/bigeye-plugin/settings.json`. Absent → `[!]` and note that running any other BigEye command will seed it.

Always exit printing the table. Never fail the session.

## Wizard Flow

Hard-fail if `MCP_AVAILABLE=false`. (The wizard depends on MCP for name → ID resolution.)

Ask one question at a time. Show the running summary after each answer.

1. **Workspace ID.** Ask: `What's your BigEye workspace_id? (integer)`. Validate integer; confirm reachability via `mcp__bigeye__list_data_sources`.
2. **Data sources.** Ask: `Filter by data source? (y/n)`. On yes: list available via MCP; user picks indices. Save resolved `[{id, name}]` to `scope.data_sources`.
3. **Schemas.** Ask: `Filter by schema? (y/n)`. On yes: per data source, list available via MCP; user picks. Save `[{id, name}]`.
4. **Tables.** Ask: `Filter by tables? (y/n)`. On yes: ask for one name per line. For each: MCP-resolve. On ambiguity → list candidates with IDs, user picks. On no match → warn, skip. Save `[{id, name}]` in `scope.tables`.
5. **Virtual tables.** Ask: `Include virtual tables? (y/n)`. Same flow as tables but filtered to virtual-table type.
6. **Monitored rules.** Ask: `Restrict to specific dimensions/rules? (y/n)`. On yes: list dimensions via `mcp__bigeye__list_dimensions`; user picks. Save `[{id, name}]`.
7. **Custom hints.** Skip in the wizard — hints are added later via `/bigeye-config hints add` once tables exist.
8. **Summary and confirmation.** Show the resolved profile JSON (truncated to first 5 entries per array). Ask:
   1. `Save this profile? (y/n)`
   2. If `y`: also ask `Also configure ~/.bigeye/config.ini for legacy CLI use? (y/n, default n)`. Pass this opt-in answer to the calling subcommand (init / add / edit), which uses it to gate the CLI section write per the `## Config Files` policy.

On `y` proceed to the caller's write step.

## Snow subcommands

Owns the `profiles[<active>].snow` block. Wraps the Snowflake `snow` CLI.

### `snow show`

```bash
snow connection list --format json
```

Read `profiles.json[active].snow`. Print as a small table:

```
Active profile: <name>
  snow.profile           : <profile> (in ~/.snowflake/config.toml)
  snow.default_warehouse : <w | "(unset; relies on ~/.snowflake/config.toml)">
  snow.default_role      : <r | "(unset)">

Connection test: ✓ pass | ✗ fail (<stderr>)
```

### `snow set <profile> [--warehouse <w>] [--role <r>]`

1. Verify the connection name exists:
   ```bash
   snow connection list --format json | python -c "import json,sys; ns=[c['connection_name'] for c in json.load(sys.stdin)]; print('OK' if '<profile>' in ns else 'MISSING')"
   ```
   `MISSING` → print "Error: connection `<profile>` not found in ~/.snowflake/config.toml. Fix: add it under `[connections.<profile>]`." and stop.
2. Run `snow connection test -c <profile>`. Non-zero → print stderr + "Fix: check the connection block in `~/.snowflake/config.toml`." and stop.
3. Update `profiles.json[active].snow = { profile, default_warehouse?, default_role? }`. Preserve unaffected fields.
4. Print confirmation.

### `snow unset`

Remove the `snow` block from `profiles.json[active]`. Confirm before write.

### `snow verify`

Run four checks, print PASS/FAIL per line:

1. `snow connection test -c <snow.profile>` → PASS on rc=0.
2. Run `SELECT 1` via:
   ```bash
   snow sql -c <snow.profile> --format json -q "SELECT 1 AS x"
   ```
   PASS on rc=0 AND parsed rows == `[{"x":1}]`.
3. `SHOW GRANTS TO ROLE <current_role>` (resolve role from `snow.default_role` or `snow sql -c <p> -q "SELECT CURRENT_ROLE()"`). Parse output via:
   ```bash
   snow sql -c <p> --format json -q "SHOW GRANTS TO ROLE <role>"
   ```
   Scan privileges for any of: `INSERT|UPDATE|DELETE|TRUNCATE|CREATE|DROP|ALTER|MERGE|GRANT|REVOKE`.
   PASS if none found; WARN otherwise. Never FAIL — warn-only.
4. Print summary line.

WARN message body (when write grants detected):
```
⚠️  warn: role <role> has write privileges on <object_count> objects.
   The engine's SQL guard will still reject non-SELECT queries, but a
   dedicated read-only role is strongly recommended.

   Example role setup (run as ACCOUNTADMIN once):
     CREATE ROLE DATA_READER;
     GRANT USAGE ON WAREHOUSE <wh>      TO ROLE DATA_READER;
     GRANT USAGE ON DATABASE <db>       TO ROLE DATA_READER;
     GRANT USAGE ON ALL SCHEMAS IN ...  TO ROLE DATA_READER;
     GRANT SELECT ON ALL TABLES IN ...  TO ROLE DATA_READER;
     GRANT ROLE DATA_READER             TO USER <you>;
```

## Errors

| Condition | Block |
|---|---|
| `snow` binary not installed | `Error: snow CLI not on PATH.` / `Fix: install Snowflake CLI (https://docs.snowflake.com/developer-guide/snowflake-cli/installation/installation).` / `Why: required for /bigeye-investigate.` |
| `~/.snowflake/config.toml` missing | `Error: ~/.snowflake/config.toml missing.` / `Fix: run snow connection add.` / `Why: snow.profile must reference a connection there.` |

## Notes

- Pretty-print JSON with 2-space indent.
- Never write comments in JSON.
- Handle `FileNotFoundError` as "no config yet."
- On JSON parse error, print the error and suggest `/bigeye-config init`.
- When editing `~/.bigeye/config.ini`, parse-preserve-rewrite: never re-order, never remove sections the plugin doesn't own, never add comments.
