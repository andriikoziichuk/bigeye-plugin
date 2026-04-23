# BigEye Plugin — Scope Loading

All BigEye skills MUST follow this document in addition to `conventions.md` to load and apply the user's active scope profile before performing any BigEye MCP calls.

---

## Step A: Locate the Config File

Path: `~/.claude/bigeye-plugin/profiles.json`

Use the `Read` tool. If the file is missing:
1. Invoke the `bigeye-config` skill with argument `init` (via the `Skill` tool).
2. After it completes, re-read the file.
3. If still missing (user cancelled the wizard), stop the current skill and print: `Aborted — no scope profile configured.`

If the JSON fails to parse:
Stop the current skill. Print:
```
Scope config at ~/.claude/bigeye-plugin/profiles.json is malformed:
{parse error}

Run `/bigeye-config init` to recreate it.
```

If the loaded profile contains a non-empty `tags` field, strip it from the working copy in memory. Print once per session: *"Note: `tags` filter removed in this plugin release — stripping from profile `<name>` on read. Next `/bigeye-config edit <name>` will rewrite without the field."* Do not modify the file on disk until the wizard rewrites it.

## Step B: Select the Active Profile

1. Parse `$ARGUMENTS` for these flags (in addition to each skill's own arguments). Remove them from the argument list before the skill processes its own args:
   - `--profile <name>`
   - `--no-scope`
   - `--workspace <id>` (integer)
2. If `--profile <name>` was given, use `profiles[<name>]`. If that key does not exist, stop and print:
   ```
   Profile `<name>` not found. Available profiles: {list}.
   ```
3. Otherwise, use `profiles[default_profile]`. If `default_profile` points to a missing key, stop and print:
   ```
   default_profile `<name>` does not exist in profiles. Available: {list}.
   Run `/bigeye-config switch <name>` to pick a valid default.
   ```
4. If the chosen profile is missing `workspace_id`, stop and print:
   ```
   Profile `<name>` has no workspace_id. Run `/bigeye-config edit <name>` to fix it.
   ```

## Step C: Apply Override Flags

- `--workspace <id>` replaces `workspace_id` in the working profile.
- `--no-scope` clears `data_source_ids`, `table_ids`, `table_names`, and `schema_names` in the working profile (workspace_id stays).
- `--profile` only affected *which* profile was loaded in Step B; no further action here.

These flags compose: a command may combine any of them.

## Step D: Resolve Table Names to IDs (once)

If the working profile has non-empty `table_names`:
1. For each name, attempt to resolve it using whichever of these MCP tools is available, in order:
   - `mcp__bigeye-knowledgebase__search_metadata`
   - `mcp__bigeye__list_tables` (or equivalent)
2. Union the resolved IDs with `table_ids`.
3. Track unresolved names for the Scope header.

Do this **once** per invocation — not before every MCP call.

## Step E: Build the Parameter Map

When calling any MCP tool that accepts these parameters (see `cli.md` Step E for the routing table), include only the non-empty fields from the working profile. For CLI calls, use the equivalent CLI flags per `cli.md` Step C (`-wid` for `data_source_ids`, `-sn` for `schema_names`, etc.).

| Profile field | MCP parameter name |
|---|---|
| `workspace_id` | `workspace_id` |
| `data_source_ids` | `data_source_ids` (if the MCP tool instead uses `source_ids`, use that name — pick whichever the tool's schema accepts) |
| `table_ids` (including resolved table_names) | `table_ids` |
| `schema_names` | `schema_names` |

Omit any parameter whose field is empty.

## Step F: Per-Skill Applicability

| Skill | Apply scope to |
|---|---|
| `bigeye-triage` | The `list_issues` call — fully scoped |
| `bigeye-coverage` | Table enumeration — only scan in-scope tables |
| `bigeye-deploy` | Default to in-scope tables unless the user names a specific target explicitly |
| `bigeye-incidents` | Issue listing + auto-cluster detection — fully scoped |
| `bigeye-rca` | Primary issue lookup (by ID) is **unscoped**. Scope applies only to lineage expansion and related-issue search |
| `bigeye-morning-report` (agent) | Same as triage — fully scoped |
| `bigeye-ticket` | Primary issue lookup is **unscoped** (user named a specific issue). Scope applies only to MCP lineage/related calls for `{{downstream_tables}}` / `{{related_issues}}` |
| `bigeye-improve` | Table argument is unscoped when named explicitly. Scope applies to MCP profile/coverage calls if their schema accepts filters; no table-list enumeration (user always names one, or the profile resolves to a single in-scope table) |

## Step F.1: CLI parameter binding

When invoking the `bigeye` CLI, pass `-w <profile_name>` so the CLI resolves its workspace section. See `cli.md` Step A for the full binding rule and `cli.md` Step E for which operations use CLI vs MCP.

## Step G: Print the Scope Header

Every skill's output MUST start with a single line `Scope:` header before any other content.

**Normal case:**
```
Scope: profile={name} · workspace={id} · sources={count} · tables={count} · schemas={count}
```

Omit any facet that is zero. Example with nothing set: `Scope: profile=full-view · workspace=42`

**With `--no-scope`:**
```
Scope: profile={name} · workspace={id} · NO-SCOPE (override)
```

**With unresolved table names:**
```
Scope: profile={name} · workspace={id} · tables=2/3 (unresolved: "orders_virtual_ltv") · sources=1
```

## Step H: Empty-Result Phrasing

When a scoped BigEye call returns zero items, the skill's output MUST distinguish scoped emptiness from generic emptiness:

- If scope filters were applied: `No active issues in scope '{profile}' — all clear.`
- If `--no-scope` was used: `No active issues — all clear.`

## Step I: Out-of-Scope RCA Soft Notice

Specific to `bigeye-rca`: if the user asks to investigate an issue by ID, fetch and analyze it unconditionally. Then, if the issue's table/data_source is outside the working profile's scope, print immediately after the `Scope:` header:

```
Note: issue {display_name} is outside the current scope '{profile}'.
```

This is informational — never refuse to analyze an explicitly-named issue.
