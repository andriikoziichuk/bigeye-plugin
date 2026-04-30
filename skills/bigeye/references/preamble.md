# BigEye Plugin — Shared Preamble

Every BigEye skill MUST follow this procedure before performing any BigEye work. This file replaces the old `scope.md` + `cli.md` + the runtime sections of `conventions.md`. Formatting (status mappings, scope pill shape, Brief/Full rules, footer, error blocks) lives in `output.md`.

The procedure has 8 ordered steps. Each step is mandatory unless explicitly marked skippable.

---

## Step 1 — Load scope profile

### 1.A Locate the file

Path: `~/.claude/bigeye-plugin/profiles.json`. Use `Read`.

If missing:
1. Invoke the `bigeye-config` skill with argument `init` (via `Skill`).
2. After it completes, re-read.
3. If still missing (user cancelled), stop the current skill and print: `Aborted — no scope profile configured.`

If the JSON fails to parse, stop and print:
```
Scope config at ~/.claude/bigeye-plugin/profiles.json is malformed:
{parse error}

Run `/bigeye-config init` to recreate it.
```

If the loaded profile contains a non-empty `tags` field, strip it from the working copy in memory. Print once per session: *"Note: `tags` filter removed in this plugin release — stripping from profile `<name>` on read. Next `/bigeye-config edit <name>` will rewrite without the field."* Do not modify the file on disk until the wizard rewrites it.

### 1.B Select the active profile

1. Parse `$ARGUMENTS` for these flags. Remove them from the argument list before the skill processes its own args:
   - `--profile <name>`
   - `--no-scope`
   - `--workspace <id>` (integer)
2. If `--profile <name>` was given, use `profiles[<name>]`. Missing key → stop and print `Profile \`<name>\` not found. Available profiles: {list}.`
3. Otherwise use `profiles[default_profile]`. Missing default key → stop and print `default_profile \`<name>\` does not exist in profiles. Available: {list}. Run \`/bigeye-config switch <name>\` to pick a valid default.`
4. Missing `workspace_id` on the chosen profile → stop and print `Profile \`<name>\` has no workspace_id. Run \`/bigeye-config edit <name>\` to fix it.`

### 1.C Apply override flags

- `--workspace <id>` replaces `workspace_id`.
- `--no-scope` clears `data_source_ids`, `table_ids`, `table_names`, `schema_names`. `workspace_id` stays.
- `--profile` only affected which profile loaded in 1.B.

These flags compose.

### 1.D Resolve table names to IDs (once)

If the working profile has non-empty `table_names`:
1. For each name, attempt to resolve via whichever MCP tool is available, in order:
   - `mcp__bigeye-knowledgebase__search_metadata`
   - `mcp__bigeye__list_tables` (or equivalent)
2. Union the resolved IDs with `table_ids`.
3. Track unresolved names for the scope pill (Step 6).

Do this **once** per invocation — not before every MCP call.

### 1.E Build the parameter map

When calling any MCP tool that accepts these parameters, include only non-empty fields:

| Profile field | MCP parameter |
|---|---|
| `workspace_id` | `workspace_id` |
| `data_source_ids` | `data_source_ids` (or `source_ids` if that's what the tool's schema accepts) |
| `table_ids` (incl. resolved `table_names`) | `table_ids` |
| `schema_names` | `schema_names` |

Omit any parameter whose field is empty.

For CLI calls, use the equivalent flags: `-wid` per `data_source_id`, `-sn` per `schema_name`, `-tid` per `table_id`. The CLI does **not** accept a `--tag` flag and does **not** accept a table-name filter — table filtering against the issue list is done post-fetch.

---

## Step 2 — Load settings

Path: `~/.claude/bigeye-plugin/settings.json`. Use `Read`.

If the file is missing, seed it silently with the defaults below and write atomically (write to `settings.json.tmp` in the same directory, then rename). Print exactly one line: `Wrote ~/.claude/bigeye-plugin/settings.json with defaults — edit via /bigeye-config settings.`

Defaults:
```json
{
  "_meta": { "version": "0.4.0", "upgrade_seen": false },
  "slack": {
    "channel": "#data-quality-alerts",
    "mention_group": "@data-oncall",
    "critical_only": true
  },
  "severity": {
    "critical_ack_hours": 4,
    "critical_related_count": 3,
    "warning_ack_hours": 24
  },
  "triage": {
    "max_issues": 50,
    "default_brief_rows": 10
  },
  "deploy": {
    "default_lookback_days": 7,
    "tag": "deployed-by-plugin"
  },
  "view": {
    "default_view": "brief"
  }
}
```

If the file exists but is missing top-level keys, use the shipped default for each missing key (forward-compatible). Do not rewrite the file on disk in that case.

If the file fails to parse, stop the skill and print:
```
Error: settings.json at ~/.claude/bigeye-plugin/settings.json is malformed.
Fix:   /bigeye-config settings show     (then re-create from the printed defaults)
Why:   {parse error}
```

`default_view` accepts `brief` or `full`. Per-invocation `--full`/`--limit` always wins. The settings file is managed only via `/bigeye-config settings show|edit <key>` — no other skill writes to it.

---

## Step 3 — Bind CLI workspace

After Step 1 has selected the active profile (e.g., `work-area`), every CLI invocation MUST pass `-w work-area`. Always pass it explicitly, even when it matches the CLI's `DEFAULT` — explicit `-w` keeps transcripts self-describing.

CLI invocation wrapper (use this exact pattern for any CLI call that produces output files):

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> <subcommand> <subargs> -op "$TMPDIR"
# parse JSON files under $TMPDIR
```

Rules:
- Always `mktemp -d`, never a fixed path.
- Cleanup the tempdir on success. On JSON parse failure, **do not delete it** — print the path for debugging instead.
- Timeouts: 60s single-issue reads, 180s bulk dumps, 300s `bigconfig apply`.
- On non-zero exit: capture stderr and print the exact command + error to the user via the `Error / Fix / Why` block defined in `output.md`.

JSON output file shapes (skills read files, never stdout):

| Command | Files produced | Key fields |
|---|---|---|
| `issues get-issues` | one JSON per issue, named by internal ID | `id`, `displayName`, `status`, `metricConfiguration.metricType`, `dimensions[]`, `events[]`, `tableName`, `columnName`, `openedAt` |
| `metric get-info` | one JSON per metric | `id`, `metricType`, `tableName`, `columnName`, `schedule`, `recentRuns[]` |
| `catalog get-metric-info` | per-metric JSONs under warehouse/schema/table tree | same as `metric get-info` |
| `catalog get-table-info` | per-table JSONs | `id`, `schemaName`, `tableName`, `columns[]`, `metricCount`, `warehouseType` |
| `bigconfig plan` | report file + fixme files | report summary for confirmation gate |
| `bigconfig apply` | apply report | success / failure counts; created metric IDs |

Exact filenames are workspace-dependent; skills enumerate via `ls "$TMPDIR"` and parse the union of JSON files.

---

## Step 4 — Detect MCP availability

Once per skill run, after Step 3:

1. Call `mcp__bigeye__list_data_sources` with `workspace_id: {profile's workspace_id}`.
2. On success: set `MCP_AVAILABLE=true`, discard the result.
3. On any error: set `MCP_AVAILABLE=false`, remember the error text.

Skills MUST check `MCP_AVAILABLE` before every MCP call. Do not retry MCP calls later in the same run — the result is authoritative.

---

## Step 5 — Apply per-skill scope rules

The per-skill matrix lives **only** here. Other skill files don't repeat it.

| Skill | Apply scope to |
|---|---|
| `bigeye-triage` | The `list_issues` call — fully scoped (post-fetch table filter; CLI has no table flag) |
| `bigeye-coverage` | Table enumeration — only scan in-scope tables |
| `bigeye-deploy` | Default to in-scope tables unless the user names a specific target explicitly |
| `bigeye-incidents` | Issue listing + auto-cluster detection — fully scoped. Explicit-ID modes honor user IDs unconditionally. |
| `bigeye-rca` | Primary issue lookup (by ID) is **unscoped**. Scope applies only to lineage expansion and related-issue search. |
| `bigeye-ticket` | Primary issue lookup is **unscoped**. Scope applies only to MCP lineage/related calls for `{{downstream_tables}}` / `{{related_issues}}`. |
| `bigeye-improve` | Table argument is unscoped when named explicitly. Scope applies to MCP profile/coverage calls if their schema accepts filters. |
| `bigeye-today` | Same as `bigeye-triage` for the issue list it composes. |
| `bigeye-table` | Table is unscoped (user named it). Scope applies to its MCP coverage call. |
| `bigeye` (dashboard) | Same as `bigeye-triage` for the issue table; iterates the active profile's tables for the "Your tables" section. `--all` widens. |
| `bigeye-morning-report` (agent) | Same as `bigeye-triage`. |

**Out-of-scope RCA soft notice:** `bigeye-rca` only — if the user asks to investigate an issue by ID, fetch and analyze unconditionally. Then, if the issue's table/data_source is outside the working profile, print after the scope pill: `Note: issue {display_name} is outside the current scope '{profile}'.` Informational only — never refuse to analyze a named issue.

---

## Step 6 — Emit the scope pill

Per `output.md` §Scope pill. The pill is the first line of skill output. Every skill MUST emit it.

---

## Step 7 — Operation routing + MCP-absent template + error rules

### 7.A Operation routing table (authoritative)

| Operation | CLI | MCP |
|---|---|---|
| List / dump issues | `issues get-issues` | — |
| Get single issue by internal ID | `issues get-issues -iid` | — |
| Resolve display-name → internal ID | — | `search_issues` (required) |
| Acknowledge / close issue | `issues update-issue` | — |
| List related issues (clustering) | — | `list_related_issues` (required) |
| Lineage trace (RCA upstream) | — | `get_issue_lineage_trace` (required) |
| Resolution steps (AI) | — | `get_resolution_steps` (required) |
| Table dimension coverage | — | `get_table_dimension_coverage` (required) |
| Column dimension coverage | — | `get_column_dimension_coverage` (required) |
| Dimension taxonomy | — | `list_dimensions` (required) |
| Table enumeration | `catalog get-table-info` | — |
| Data-source listing | — | `list_data_sources` (required) |
| Deploy — bulk / gaps | `bigconfig plan` + `apply` | — |
| Deploy — freshness / explicit columns | `metric upsert -t SIMPLE` | — |
| Tag CRUD | — | `list_tags` / `create_tag` / `tag_entity` (required) |
| Create / merge incident | — | `create_incident` (required) |
| Table profile data | — | `get_table_profile` (required) |

### 7.B MCP-absent warning template

When a skill would call MCP but `MCP_AVAILABLE=false`, emit the `Error / Fix / Why` block defined in `output.md`. Use:

```
Error: MCP server unavailable — {feature_name} skipped.
Fix:   See bigeye-mcp-install.md to enable MCP.
Why:   {error captured in Step 4}
```

Populate `{feature_name}` from the per-skill table:

| Skill | feature_name (per skipped step) |
|---|---|
| `bigeye-triage` | cluster detection |
| `bigeye-rca` | display-name lookup / lineage trace / related issues / resolution steps |
| `bigeye-coverage` | dimension coverage scoring |
| `bigeye-deploy` | coverage-driven deploy planning / per-column dimension inference / monitor tagging |
| `bigeye-incidents` | display-name lookup / relationship validation / cluster auto-detection / incident creation |
| `bigeye-ticket` | display-name lookup / downstream tables / related issues / resolution steps |
| `bigeye-improve` | missing-coverage suggestions / profile refinement |
| `bigeye-today` | (delegates — uses each skill's feature_name) |
| `bigeye-table` | dimension coverage scoring (for the status card) |
| `bigeye-morning-report` | cluster detection / coverage scoring |

If the skill has a CLI-only workaround, append it as a second `Fix:` line. Continue or hard-fail per the per-skill behavior matrix in 7.C.

### 7.C Per-skill MCP-absence behavior

| Skill | Uses CLI for | Uses MCP for | On MCP absence |
|---|---|---|---|
| `bigeye-triage` | issue listing | cluster detection | cluster section replaced with note; rest renders |
| `bigeye-rca` | issue details by ID | display-name lookup, lineage, related, resolution | display-name hard-fails unless `--internal-id`; lineage/related/resolution skipped |
| `bigeye-coverage` | issue history | dimension coverage scoring | hard-fail with pointer |
| `bigeye-deploy` (gaps/bulk) | bigconfig plan/apply | coverage discovery, tag ops | hard-fail (coverage unavailable) |
| `bigeye-deploy` (freshness) | metric upsert | tag ops | works; tagging skipped |
| `bigeye-deploy` (columns) | metric upsert | per-column dimension inference, tag ops | works only with `--metric-type`; tagging skipped |
| `bigeye-incidents` (close) | update-issue | display-name lookup | close works with `--internal-id` |
| `bigeye-incidents` (create/auto) | issue listing | create_incident, related, display-name | create hard-fails |
| `bigeye-improve` | metric/issue dump | profile + coverage | weak-monitor scan still runs; coverage suggestions skipped |
| `bigeye-ticket` | issue details | display-name + lineage/related/resolution | display-name hard-fails unless `--internal-id`; MCP-only `{{vars}}` substituted with `_(unavailable — MCP not configured)_` |
| `bigeye-today` | issue listing | clustering, display-name | cluster column shows `—`; otherwise as triage |
| `bigeye-table` | issue listing on the table | coverage, name resolution | bare-name resolution hard-fails (require fully-qualified); coverage shows `—` |
| `bigeye-morning-report` | issue listing | clustering, coverage | cluster/coverage sections replaced with notes |

### 7.D Error-handling rules

Use the `Error / Fix / Why` block defined in `output.md` for every user-facing error.

- CLI auth error (stderr contains `401` or `Config file not found`):
  ```
  Error: BigEye CLI auth not configured.
  Fix:   /bigeye-config init
  Why:   No ~/.bigeye/credentials file found.
  ```
- Scope error (CLI returns `404` or `No such warehouse`):
  ```
  Error: BigEye CLI rejected workspace/warehouse — {short stderr}.
  Fix:   /bigeye-config show
  Why:   The CLI's workspace section may not match the active profile.
  ```
- JSON parse error on `-op` output: do not delete the tempdir. Print:
  ```
  Error: failed to parse CLI JSON at <path>.
  Fix:   Re-run with --verbose, then paste the file contents for diagnosis.
  Why:   {parser exception}
  ```
- Partial write success: report success count + failed items; skip chaining suggestions until fixed.

Under `--verbose`, append the `Details:` block per `output.md` §Error format.

---

## Step 8 — State persistence (write on success)

Path: `~/.claude/bigeye-plugin/state.json`.

### 8.A On entry

`Read` the file. If missing or empty, treat as:
```json
{ "_meta": { "version": "0.4.0" }, "issues": {}, "tables": {}, "last_issue": null, "last_table": null, "last_workflow": null }
```

If `_meta.version` is missing or stale, replace with `"0.4.0"`.

### 8.B On successful skill completion

Each skill defines what it writes. Append to `actions[]` of the relevant issue and/or table. Update `last_*` pointers.

Schema:

```json
{
  "_meta": { "version": "0.4.0" },
  "last_issue": "10921",
  "last_table": "warehouse.public.orders",
  "last_workflow": "today",
  "issues": {
    "10921": {
      "internal_id": 42,
      "display_name": "10921",
      "first_seen": "2026-04-20T09:12:00Z",
      "last_seen": "2026-04-24T14:03:00Z",
      "status_when_last_seen": "ACKNOWLEDGED",
      "actions": [
        { "skill": "bigeye-rca", "at": "2026-04-20T09:14:00Z" }
      ]
    }
  },
  "tables": {
    "warehouse.public.orders": {
      "first_seen": "2026-04-18T08:00:00Z",
      "last_seen": "2026-04-24T09:15:00Z",
      "actions": [
        { "skill": "bigeye-coverage", "at": "2026-04-18T08:02:00Z" }
      ]
    }
  }
}
```

Per-skill writes (atomic skills):

| Skill | last_issue | last_table | issues[id].actions append | tables[fq].actions append | Notes |
|---|---|---|---|---|---|
| `bigeye-triage` | — | — | — | — | Updates `last_seen` + `status_when_last_seen` for every listed issue. |
| `bigeye-rca` | yes (display_name) | yes (table) | yes — `{ skill: "bigeye-rca", at: <iso> }` | yes — same | Sets `internal_id` on the issue if known. |
| `bigeye-coverage` | — | yes | — | yes — `{ skill: "bigeye-coverage", at: <iso> }` | |
| `bigeye-improve` | — | yes | — | yes — `{ skill: "bigeye-improve", at: <iso> }` | |
| `bigeye-deploy` | — | yes (when target was a table) | — | yes — `{ skill: "bigeye-deploy", at: <iso>, note: "<N monitors created>" }` | Only on successful apply. |
| `bigeye-incidents` | yes (last issue grouped) | — | yes — `{ skill: "bigeye-incidents", at: <iso>, note: "grouped with <list>" }` per merged issue | — | |
| `bigeye-ticket` | yes | — | yes — `{ skill: "bigeye-ticket", at: <iso> }` | — | |
| `bigeye-today` | yes (last issue user picked) | — | (delegated skills already wrote) | (delegated skills already wrote) | Sets `last_workflow="today"`. |
| `bigeye-table` | — | yes (the table) | (delegated) | (delegated) | Sets `last_workflow="table"`. |

Writes are atomic: write `state.json.tmp` in the same directory, then rename.

### 8.C Pruning (LRU)

After write, if `len(issues) > 500` or `len(tables) > 100`, drop entries by oldest `last_seen` until under the cap. Pruning runs at the end of any skill that wrote.

### 8.D No-arg fallbacks

- `/bigeye-rca` with no issue argument → use `state.last_issue`. Empty → ask the user.
- `/bigeye-coverage` with no table argument → use `state.last_table`. Empty → fall back to the existing scope-driven enumeration.
- `/bigeye-improve` with no table argument → use `state.last_table`. Empty → ask the user.
- `/bigeye-table` with no name → use `state.last_table`. Empty → list top 5 recent in-scope tables from `state.tables`.

### 8.E Upgrade notice (one-time)

After settings load (Step 2) and before any skill output, check `settings.json._meta.upgrade_seen`. If `false`:

1. Print exactly:
   ```
   Upgraded to bigeye-plugin 0.4.0. New: /bigeye (dashboard), /bigeye-today, /bigeye-table.
   Your profiles and templates are preserved. See README or run /bigeye for a tour.
   ```
2. Set `_meta.upgrade_seen` to `true`. Write atomically.

If `true`, skip silently. Prints exactly once across the user's lifetime of running 0.4.0.

---

## End of preamble

Skills resume their own logic after Step 8 setup. State writes (8.B) happen at the end of the skill's successful run, not at the start.
