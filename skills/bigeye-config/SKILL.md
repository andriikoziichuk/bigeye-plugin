---
name: bigeye-config
description: Use when the user wants to configure the BigEye plugin's scope (workspace + filters), run the first-run wizard, manage named profiles, or verify CLI/MCP setup. Also auto-invoked by other BigEye skills when the config file is missing.
user-invocable: true
---

# BigEye Configuration

Owns the per-user profiles file at `~/.claude/bigeye-plugin/profiles.json` AND the matching workspace sections of `~/.bigeye/config.ini`. This is the **only** skill that writes to either file.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for shared output formatting and `skills/bigeye/references/cli.md` for CLI invocation rules.

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
| `verify` / `verify <name>` | Run a four-point health check (CLI install, CLI workspace, CLI auth, MCP reachability) and print a status table |

## Config Files

**`~/.claude/bigeye-plugin/profiles.json`** — plugin-owned; contains profile definitions + default pointer.

**Schema** (note: `tags` field removed in this version):

```json
{
  "default_profile": "work-area",
  "profiles": {
    "work-area": {
      "workspace_id": 42,
      "data_source_ids": [17],
      "table_ids": [],
      "table_names": ["orders_main"],
      "schema_names": []
    }
  }
}
```

**`~/.bigeye/config.ini`** — plugin writes the section matching the profile name:

```ini
[work-area]
workspace_id = 42
```

**`~/.bigeye/credentials`** — user-owned, never touched by the plugin.

**Field rules:**
- `default_profile` must reference a key in `profiles`.
- Each profile requires `workspace_id`. All other fields are optional arrays.
- Missing filter fields default to empty arrays when written.
- `tags` is removed — see migration below.

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
6. Add/replace the `[<profile>]` section in `~/.bigeye/config.ini` with `workspace_id = <id>` (leave all other sections untouched). If `~/.bigeye/config.ini` doesn't exist, create it with only the new section (no implicit `[DEFAULT]`).
7. Verify CLI binding:
   ```bash
   bigeye -w <profile> configure list
   ```
   On non-zero exit, print the CLI error and a note:
   *"CLI workspace configured, but `bigeye configure list` failed. You likely need to set up `~/.bigeye/credentials` via `bigeye configure` or by following `bigeye-cli-install.md`."*
8. Print:
   ```
   Wrote profile `{name}` to:
     ~/.claude/bigeye-plugin/profiles.json (set as default)
     ~/.bigeye/config.ini (section [{name}], workspace_id={id})

   Try `/bigeye-config verify` to confirm setup, then `/bigeye-triage` for scoped issues.
   ```

### Subcommand: `add <name>`

1. Validate `<name>` per Profile-Name Validation rules.
2. Read existing `profiles.json`. If missing, tell the user to run `/bigeye-config init` first.
3. If `[<name>]` already exists in `~/.bigeye/config.ini`, print current contents and ask:
   *"A CLI section `[<name>]` already exists with workspace_id=<X>. Overwrite with the new profile's workspace_id? (y/n/pick-different-name)"*.
4. Run the Wizard Flow.
5. Merge new profile into `profiles`. Do not change `default_profile`.
6. Add/replace `[<name>]` in `~/.bigeye/config.ini`.
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
5. Write `profiles.json`. Update `[<name>]` in `~/.bigeye/config.ini` with the new `workspace_id`.
6. Print confirmation.

### Subcommand: `delete <name>`

1. Read file. If missing or `<name>` not in `profiles`, error.
2. If `<name>` is the `default_profile`:
   - If only one profile exists: refuse. Print the standard error and stop.
   - Otherwise: ask which profile to promote as the new default.
3. Ask confirmation: *"Also remove `[<name>]` from `~/.bigeye/config.ini`? (y/n) — Other tools on this machine may be using this section."*
4. Remove profile from `profiles.json`. If user confirmed, remove the section from `config.ini`.
5. Write file(s). Print confirmation listing exactly what was removed.

### Subcommand: `verify` / `verify <name>`

Resolve the profile name (argument or active default). Print:

```
BigEye Plugin — Setup Status

[{a}] CLI installed            {bigeye --version output or "not on PATH"}
[{b}] CLI workspace configured [{profile}] → workspace_id={id} (~/.bigeye/config.ini)
[{c}] CLI auth                 {~/.bigeye/credentials status}
[{d}] MCP server reachable     {MCP probe result}
                              {when reachable: feature list enabled by MCP}

Overall: {ready / partially degraded / setup required}
```

Status markers use plain ASCII: `[✓]` (good), `[!]` (warn), `[✗]` (fail), `[~]` (info).

Check steps:
- **a**: run `which bigeye`. If non-zero, mark `[✗]` and suggest `bigeye-cli-install.md`.
- **b**: read the resolved profile's `workspace_id`, confirm `[<profile>]` exists in `~/.bigeye/config.ini` with that value. Mismatch → `[!]`.
- **c**: `test -r ~/.bigeye/credentials`. Absent → `[!]`, point at `bigeye configure`.
- **d**: call `mcp__bigeye__list_data_sources` with `workspace_id`. On success, list the features MCP unlocks. On failure, mark `[!]` and point at `bigeye-mcp-install.md`.

Always exit printing the table. Never fail the session.

## Wizard Flow

Ask one question at a time. Show the running summary after each answer.

1. **Workspace ID.** Ask: *"What's your BigEye workspace_id? (integer)"*. Validate integer. If `mcp__bigeye__list_data_sources` is available, call with `workspace_id: {answer}` to confirm reachability; warn but don't block on error.
2. **Data sources.** Ask: *"Filter by data source? (y/n)"*.
   - If yes and MCP is available: call `mcp__bigeye__list_data_sources`, show as numbered list, let user pick indices. Store resolved integer IDs in `data_source_ids`.
   - If yes and MCP is absent: print *"MCP not available — enter warehouse IDs one per line (blank to finish). Find these in the BigEye UI under Settings → Sources."* Store the integers in `data_source_ids`.
3. **Tables.** Ask: *"Filter by specific tables? (y/n)"*. If yes, ask for one name per line. Resolve via whichever MCP tool is available (`mcp__bigeye-knowledgebase__search_metadata` or `mcp__bigeye__list_tables`). Store names in `table_names` and resolved IDs in `table_ids`. Warn on unresolved names; don't block.
4. **Schemas.** Ask: *"Filter by schema? (y/n)"*. Store in `schema_names`.
5. **Summary and confirmation.** Show:
   ```
   Profile summary:
     workspace_id: {...}
     data_source_ids: [...]
     table_names: [...]
     table_ids: [...]
     schema_names: [...]

   Will write:
     ~/.claude/bigeye-plugin/profiles.json (profile '{name}')
     ~/.bigeye/config.ini (section [{name}], workspace_id={id})

   Save this profile? (y/n)
   ```
   On `n`, restart. On `y`, proceed to the caller's write step.

Tags are NOT asked — the field is removed.

## Notes

- Pretty-print JSON with 2-space indent.
- Never write comments in JSON.
- Handle `FileNotFoundError` as "no config yet."
- On JSON parse error, print the error and suggest `/bigeye-config init`.
- When editing `~/.bigeye/config.ini`, parse-preserve-rewrite: never re-order, never remove sections the plugin doesn't own, never add comments.
