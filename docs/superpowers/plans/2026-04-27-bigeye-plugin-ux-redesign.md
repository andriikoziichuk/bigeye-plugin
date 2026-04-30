# BigEye Plugin — UX Redesign (v0.4.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the BigEye plugin's nine-skill surface into two primary workflow commands (`/bigeye-today`, `/bigeye-table`) plus a persistent dashboard (`/bigeye`), backed by a consolidated reference layer (`preamble.md` + `output.md`), a user-owned `settings.json`, and an append-only `state.json` activity log.

**Architecture:** Two new skills (`bigeye-today`, `bigeye-table`) compose the existing atomic skills (`bigeye-triage`, `bigeye-rca`, `bigeye-coverage`, `bigeye-improve`, `bigeye-deploy`, `bigeye-incidents`, `bigeye-ticket`) without duplicating their logic. Every atomic skill is rewritten to read a single `preamble.md` (replacing `scope.md` + `cli.md`) and a single `output.md` (replacing the formatting parts of `conventions.md`). User-editable config moves out of plugin files into `~/.claude/bigeye-plugin/settings.json`. A new `~/.claude/bigeye-plugin/state.json` records issue/table activity for no-arg fallbacks (`last_issue`, `last_table`) and dashboard "History" columns. `/bigeye` itself is rewritten as the dashboard. The morning-report agent calls `/bigeye-today --report-only` instead of duplicating triage logic. Backwards-compatible on disk: `profiles.json` and ticket templates are unchanged.

**Tech Stack:** Markdown skill files only. JSON for `settings.json`, `state.json`, and the plugin manifest. INI for the BigEye CLI config (untouched by this plan). No source code, no test framework — verification is manual.

**Spec reference:** `docs/superpowers/specs/2026-04-24-bigeye-plugin-ux-redesign-design.md`

**Commit policy:** Every task ends with a `git add` step ("Stage"). Plan tasks NEVER run `git commit` — the user owns all commits. Batching multiple tasks into one commit is the user's choice.

---

## File Structure

**New files (created by this plan):**

| Path | Created in | Responsibility |
|---|---|---|
| `skills/bigeye/references/preamble.md` | Task 1 | Single ordered procedure every skill runs before its own work: load scope, load settings (seed if missing), bind CLI workspace, detect MCP, apply per-skill scope rules, emit scope pill, MCP-absent warning template, error format rules, state-persistence procedure, upgrade notice. |
| `skills/bigeye/references/output.md` | Task 2 | Single source for formatting: status/priority display mapping, severity classes, scope-pill format, Brief/Full rules, `Next:`/`More:` footer, `Error / Fix / Why` block, picker prompt shape, progress indicators, global flag catalog. No config values. |
| `skills/bigeye-today/SKILL.md` | Task 14 | Reactive workflow — interactive loop: list open issues → pick → action menu → delegate → return. Also `--report-only` non-interactive mode used by the morning-report agent. |
| `skills/bigeye-table/SKILL.md` | Task 15 | Proactive workflow — pick a table → status card → action menu → delegate → return. No-arg form falls back to `state.json.last_table`. |

**Modified files (rewrites — every line is replaced):**

| Path | Modified in | Responsibility |
|---|---|---|
| `skills/bigeye/SKILL.md` | Task 13 | Rewritten as the dashboard. No more intent routing — `/bigeye` always renders status. Free-text trailing args → "Did you mean …?" hint above the dashboard. |
| `skills/bigeye-config/SKILL.md` | Task 3 | Extended with `settings show` / `settings edit <key> <value>` subcommands. Owns `~/.claude/bigeye-plugin/settings.json` (alongside the existing `profiles.json`). |
| `skills/bigeye-triage/SKILL.md` | Task 6 | Rewritten to use `preamble.md` + `output.md`. Brief by default. New `Error / Fix / Why` block. New `Next:`/`More:` footer. Scope pill replaces the `Scope:` line. State-persistence line at the end. |
| `skills/bigeye-rca/SKILL.md` | Task 7 | Same rewrite. Plus: no-arg form reads `state.json.last_issue`. |
| `skills/bigeye-coverage/SKILL.md` | Task 8 | Same rewrite. Plus: no-arg form reads `state.json.last_table`. |
| `skills/bigeye-improve/SKILL.md` | Task 9 | Same rewrite. Plus: no-arg form reads `state.json.last_table`. Heavy-mode SQL paste protocol unchanged in behavior. |
| `skills/bigeye-deploy/SKILL.md` | Task 10 | Same rewrite. Confirmation gate text unchanged. Defaults (`lookback_days`, `tag`) read from `settings.json.deploy`. |
| `skills/bigeye-incidents/SKILL.md` | Task 11 | Same rewrite. |
| `skills/bigeye-ticket/SKILL.md` | Task 12 | Same rewrite. Output, error, footer formats updated. |
| `agents/bigeye-morning-report.md` | Task 16 | Retargeted to call `/bigeye-today --report-only`, then add coverage scoring (current Step 3) and Slack notification (current Step 5). Slack settings read from `settings.json.slack`. |
| `README.md` | Task 17 | Leads with the two workflow commands + dashboard. Adds a "What changed in 0.4.0" section. |
| `.claude-plugin/plugin.json` | Task 17 | `version`: 0.3.0 → 0.4.0. |
| `.claude-plugin/marketplace.json` | Task 17 | `plugins[0].version`: 0.3.0 → 0.4.0. |

**Stubbed mid-rollout, deleted at the end:**

| Path | Stubbed in | Final state |
|---|---|---|
| `skills/bigeye/references/scope.md` | Task 4 | Deleted in Task 17 |
| `skills/bigeye/references/cli.md` | Task 4 | Deleted in Task 17 |
| `skills/bigeye/references/conventions.md` | Task 4 | Deleted in Task 17 |

**Unchanged (not touched by this plan):**

- `skills/bigeye/references/improve.md`
- `skills/bigeye-ticket/templates/default.md`
- `bigeye-cli-install.md`
- `bigeye-mcp-install.md`
- `hooks/hooks.json`
- `~/.bigeye/config.ini`
- `~/.bigeye/credentials`
- `~/.claude/bigeye-plugin/profiles.json` (schema — already user-owned)
- `~/.claude/bigeye-plugin/ticket-templates/*.md`

**Order rationale:** The reference files (preamble.md, output.md) come first because every later skill cites them. `/bigeye-config` extension comes next so `settings.json` seeding works before any atomic skill runs. The reference stubs (Task 4) keep the old skill files functional during the in-flight rewrite. Atomic skills are rewritten next (Tasks 6–12), one per skill; each rewrite makes that skill use the new references plus state-writes plus no-arg fallbacks. The dashboard (Task 13) and the two workflows (Tasks 14–15) come after the atomic skills they delegate to. The agent retarget (Task 16) follows once `/bigeye-today --report-only` exists. Final task batches version bump + README + upgrade-notice wiring + reference-stub deletion + manual verification.

**No automated test files** — every skill is markdown. Verification is manual per spec §Verification. Task 18 is the checklist.

---

## Task 1: Create `preamble.md` — single shared procedure

**Files:**
- Create: `skills/bigeye/references/preamble.md`

**Context:** Today every skill opens with three preamble references (`conventions.md`, `scope.md`, `cli.md`). The redesign collapses scope + CLI behavior into one ordered procedure, layers in settings/state, and pushes formatting into `output.md` (Task 2).

The new file contains 8 ordered steps. Steps 1–7 fold in today's `scope.md` Steps A–I and `cli.md` Steps A–H. Step 8 is new: state.json append + prune + upgrade notice.

- [ ] **Step 1: Write the file**

Write `skills/bigeye/references/preamble.md` with exactly this content:

````markdown
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
````

- [ ] **Step 2: Verify the file exists and is well-formed**

Run:
```bash
wc -l skills/bigeye/references/preamble.md
grep -c "^## Step" skills/bigeye/references/preamble.md
```

Expected: roughly 270–350 lines; exactly 8 lines matching `^## Step `.

- [ ] **Step 3: Stage**

```bash
git add skills/bigeye/references/preamble.md
```

(Do not commit. The user owns commits.)

---

## Task 2: Create `output.md` — single formatting reference

**Files:**
- Create: `skills/bigeye/references/output.md`

**Context:** Today, `conventions.md` mixes formatting rules (status display, severity classes, table shapes) with config (Slack channel, severity thresholds). The redesign splits these: formatting goes here; config moves to `settings.json` (already wired in Task 1's Step 2).

`output.md` is the **only** place formatting lives.

- [ ] **Step 1: Write the file**

Write `skills/bigeye/references/output.md` with exactly this content:

````markdown
# BigEye Plugin — Output & Formatting

Every BigEye skill MUST follow these rules for output shape. Configuration values (Slack channel, severity thresholds, deploy defaults) live in `settings.json`, not here.

---

## Status display mapping

| API status | Display |
|---|---|
| `ISSUE_STATUS_NEW` | New |
| `ISSUE_STATUS_ACKNOWLEDGED` | Ack'd |
| `ISSUE_STATUS_CLOSED` | Closed |
| `ISSUE_STATUS_MONITORING` | Monitoring |
| `ISSUE_STATUS_MERGED` | Merged |

## Priority display mapping

| API priority | Display |
|---|---|
| `ISSUE_PRIORITY_LOW` | Low |
| `ISSUE_PRIORITY_MED` | Medium |
| `ISSUE_PRIORITY_HIGH` | High |

## Severity classification

Used by skills that bucket issues. Thresholds come from `settings.json.severity`.

**Critical:**
- Freshness or Volume dimension issues (pipeline broken).
- Any issue older than `severity.critical_ack_hours` (default 4) still in NEW status.
- Any issue with `severity.critical_related_count` (default 3) or more related downstream issues.

**Warning:**
- Data quality dimension issues (Validity, Completeness, Uniqueness).
- Issues with 1–2 related downstream issues.
- Issues in ACKNOWLEDGED status older than `severity.warning_ack_hours` (default 24).

**Low:**
- Recently opened issues (< 1 hour) with no related issues.
- Distribution or Format dimension issues with no downstream impact.
- Issues already in MONITORING status.

Severity prefix in summary text: bold word — **Critical**, **Warning**, **Low**. No emoji unless the user explicitly asked.

## Closing labels

When closing issues via the CLI (`bigeye issues update-issue -cl <label>`):
- `TRUE_POSITIVE` — Real issue, now resolved.
- `FALSE_POSITIVE` — Not a real issue (noisy monitor).
- `EXPECTED` — Known exception.

User-facing shorthand to CLI mapping. Note: the `true-negative` → `TRUE_POSITIVE` mapping is intentional — kept for backward compatibility with prior plugin versions.

| Shorthand (`--label`) | CLI label |
|---|---|
| `true-negative` | `TRUE_POSITIVE` |
| `false-positive` | `FALSE_POSITIVE` |
| `expected` | `EXPECTED` |

## Tag conventions

- `deployed-by-plugin` (default; override via `settings.json.deploy.tag`): applied to all monitors created via `/bigeye-deploy`.
- Before tagging, call `mcp__bigeye__list_tags` with `search: "<tag>"`. If not found, create with `mcp__bigeye__create_tag` (`name: "<tag>"`, `color_hex: "#6366F1"`).

---

## Scope pill (line 1 of every skill)

Format: `[<profile> · <workspace_id> · <non-empty-facets>]`

Examples:
- `[my-area · 42 · 3 tables]`
- `[my-area · 42 · 3 tables · 1 source]`
- `[my-area · 42 · NO-SCOPE]`
- `[my-area · 42 · 2/3 tables]` (1 unresolved)

Rules:
- Omit facets whose count is zero.
- Single-line only; no prefix word; flush left.
- If scope has unresolved table names, append `(unresolved: "<name1>")` after the pill on the same line.
- Under `--no-scope`: render `NO-SCOPE` as the only facet (in addition to profile + workspace).

## Brief vs Full output

Every skill that renders a list of rows defaults to **Brief**: top `triage.default_brief_rows` (default 10) rows + summary. Override:
- `--full` — show all rows.
- `--limit N` — show top N rows (`N` is an integer).
- `settings.json.view.default_view = "full"` — make Full the default for every skill.

Per-invocation flags always win over the settings default.

Under Brief, after the displayed rows, when there are more rows:
```
(<N more> — add --full to see all)
```

Only print this line when there actually are more rows.

## Next / More footer

Every skill output ends with a 2-line block:

```
Next: <single best action, with the exact command inline>     (<short reason>)
More: <2-4 alternatives, · separated>
```

Examples:
- Triage: `Next: /bigeye-rca 10921     (top-scored, not yet investigated)`
- Coverage: `Next: /bigeye-deploy gaps --priority high     (3 high-priority gaps)`
- Deploy: `Next: /bigeye-triage     (verify in ~1 hour)`

Rules:
- `Next` is always a single command. Always include a parenthetical reason.
- `More` is 2–4 commands, `·` separated, no reasons. Skills pick the most likely alternates.

## Error format

Every user-facing error uses this 3-line block:

```
Error: <one-line cause>
Fix:   <exact command to run>
Why:   <one-line reason>
```

Under `--verbose`, append:

```
Details:
  command: <exact CLI that ran>
  stderr:  <full stderr>
  path:    <relevant file path>
```

When the skill has multiple parallel fixes (e.g., MCP-absent with a CLI workaround):

```
Error: <one-line cause>
Fix:   <primary command>
Fix:   <alternate command>     (<one-line condition>)
Why:   <one-line reason>
```

## Empty-result phrasing

When a scoped BigEye call returns zero items:
- If scope filters were applied: `No active issues in scope '{profile}' — all clear.`
- If `--no-scope` was used: `No active issues — all clear.`

## Picker prompt

```
Pick: [1-N], [a]ll, [q]uit
> _
```

Rules:
- Instructions on one line, prompt arrow `> _` on its own line below.
- Brackets indicate single-key shortcuts. Numbers indicate range.
- Per-skill picker rows may add tokens (e.g., `[c]lusters`, `<display_name>`, `/<slash_command>`).

## Progress indicators

Long-running multi-step skills (`bigeye-improve` heavy mode, `bigeye-deploy` bigconfig plan+apply) print numbered progress on **step transitions only**:

```
[1/4] Fetching metrics ...
[2/4] Scoring heuristics ...
[3/4] Drafting SQL bundle ...
[4/4] Waiting for paste-back
```

No spinners. Transitions only.

## Issue table column format

Used by `bigeye-triage`, `bigeye-today`, `bigeye` (dashboard), and any skill that lists issues. Standard columns:

```
 # | Issue | Score | Dim | Table | Column | Since | History
```

Variants — skills may add columns to the right (e.g., `Alerts`, `First run`) when justified, but never reorder the leading columns.

- `#` — sequential row number
- `Issue` — display name (the number shown in BigEye UI)
- `Score` — `priorityScore` (0–100 from BigEye)
- `Dim` — `metricConfiguration.dimension.displayName`
- `Table` — `metricMetadata.datasetName`, last segment only
- `Column` — `metricMetadata.fieldName`, or `—` for table-level metrics
- `Since` — human-readable time since `openedAt` (e.g., `2h`, `3d`)
- `History` — short skill tags + age from `state.json.issues[<id>].actions`, last 2 distinct skills, comma-separated. Format: `rca (4d)`, `inc (3d)`. Empty → `—`.

## Cheatsheet line conventions (dashboard / morning report)

When emitting a command list:
- One command per line, left-aligned.
- Description column starts at column 33 (single space-separated; pad as needed).
- Stable wording across runs — never reorder.

## Global flag catalog (every skill)

Documented once here; skill argument tables don't repeat the descriptions:

| Flag | Effect |
|---|---|
| `--profile <name>` | Use a specific profile for this run instead of `default_profile`. |
| `--no-scope` | Clear scope filters (workspace_id stays). |
| `--workspace <id>` | Override workspace_id for this run. |
| `--full` | Render Full instead of Brief. |
| `--limit N` | Render top N rows. |
| `--verbose` | Append the `Details:` block to error blocks. |

Skill argument tables use this 3-column shape:

```markdown
| Invocation | Purpose | Example |
|---|---|---|
| `(no arg)` | Default behavior | `/bigeye-rca` |
```
````

- [ ] **Step 2: Verify shape**

Run:
```bash
grep -c "^## " skills/bigeye/references/output.md
```

Expected: at least 13 sections (Status mapping, Priority mapping, Severity, Closing labels, Tag conventions, Scope pill, Brief vs Full, Next / More footer, Error format, Empty-result phrasing, Picker prompt, Progress indicators, Issue table, Cheatsheet, Global flag catalog).

- [ ] **Step 3: Stage**

```bash
git add skills/bigeye/references/output.md
```

---

## Task 3: Extend `/bigeye-config` with `settings show|edit`

**Files:**
- Modify: `skills/bigeye-config/SKILL.md`

**Context:** The wizard subcommands (`init`, `add`, `switch`, `edit`, `delete`, `verify`) already exist and own `profiles.json`. We extend the same skill to own `settings.json` via two new subcommands. We also retarget the preamble line: this skill now reads `preamble.md` (the new shared file) instead of `conventions.md` + `cli.md`.

- [ ] **Step 1: Replace the SKILL.md preamble line**

Replace the line at `skills/bigeye-config/SKILL.md:11`:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for shared output formatting and `skills/bigeye/references/cli.md` for CLI invocation rules.
```

with:
```
**Before doing anything else**, follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection. Output shape lives in `skills/bigeye/references/output.md`.
```

- [ ] **Step 2: Add `settings` subcommand rows to the Arguments table**

In `skills/bigeye-config/SKILL.md`, locate the `## Arguments` table (around line 14–26). Append these rows immediately before the `verify` row:

```
| `settings show` | Print the merged effective settings (file values + shipped defaults for any missing keys) |
| `settings edit <key> <value>` | Overwrite a single dotted-path key in `~/.claude/bigeye-plugin/settings.json` |
```

- [ ] **Step 3: Add the settings file documentation**

After the `## Config Files` section, before the `## Profile-Name Validation` section, insert this block:

````markdown
## Settings File

`~/.claude/bigeye-plugin/settings.json` — plugin-owned; user-editable via the `settings show` / `settings edit` subcommands. Schema (defaults shown):

```json
{
  "_meta": { "version": "0.4.0", "upgrade_seen": false },
  "slack": { "channel": "#data-quality-alerts", "mention_group": "@data-oncall", "critical_only": true },
  "severity": { "critical_ack_hours": 4, "critical_related_count": 3, "warning_ack_hours": 24 },
  "triage": { "max_issues": 50, "default_brief_rows": 10 },
  "deploy": { "default_lookback_days": 7, "tag": "deployed-by-plugin" },
  "view": { "default_view": "brief" }
}
```

`settings.json` is seeded by `preamble.md` Step 2 on first encounter. This skill is the only one that **edits** the file directly.
````

- [ ] **Step 4: Add subcommand procedures**

In `skills/bigeye-config/SKILL.md`, before the `### Subcommand: \`verify\`` section, insert these two new sections:

````markdown
### Subcommand: `settings show`

1. `Read` `~/.claude/bigeye-plugin/settings.json`. If missing, follow `preamble.md` Step 2 to seed defaults, then re-read.
2. Print:
   ```
   ## BigEye Plugin Settings

   ~/.claude/bigeye-plugin/settings.json

   {pretty-printed JSON, 2-space indent, keys in canonical order: _meta, slack, severity, triage, deploy, view}
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
````

- [ ] **Step 5: Update the verify subcommand to mention settings**

In `skills/bigeye-config/SKILL.md`, in the `### Subcommand: \`verify\`` block, add a fifth status row to the printed table (between `[d]` and the `Overall:` line):

```
[{e}] Settings file               {settings.json: present / missing}
```

Check step **e**: `test -r ~/.claude/bigeye-plugin/settings.json`. Absent → `[!]` and note that running any other BigEye command will seed it.

- [ ] **Step 6: Verify the file**

```bash
grep -c "^### Subcommand:" skills/bigeye-config/SKILL.md
grep -c "settings show\|settings edit" skills/bigeye-config/SKILL.md
```

Expected: at least 8 subcommand sections (was 6, plus `settings show`, `settings edit`); at least 4 mentions of `settings show` / `settings edit`.

- [ ] **Step 7: Stage**

```bash
git add skills/bigeye-config/SKILL.md
```

---

## Task 4: Stub the old reference files

**Files:**
- Modify: `skills/bigeye/references/scope.md`
- Modify: `skills/bigeye/references/cli.md`
- Modify: `skills/bigeye/references/conventions.md`

**Context:** Per spec rollout step 1: "Do not delete the old reference files yet; leave them as one-line stubs pointing at the new files." Atomic skills haven't been rewritten yet (Tasks 6–12), and they still reference these files via the old preamble paragraph. Stubs guarantee that any read still resolves to actionable text. Final deletion happens in Task 17.

- [ ] **Step 1: Replace `scope.md` with a stub**

Overwrite `skills/bigeye/references/scope.md` with exactly:

```markdown
# BigEye Plugin — Scope (moved)

This file has moved. Follow `skills/bigeye/references/preamble.md` Step 1 (scope load), Step 5 (per-skill scope rules), and Step 6 (scope pill).

This stub will be removed in a future plugin release. Do not link to it.
```

- [ ] **Step 2: Replace `cli.md` with a stub**

Overwrite `skills/bigeye/references/cli.md` with exactly:

```markdown
# BigEye Plugin — CLI / MCP routing (moved)

This file has moved. Follow `skills/bigeye/references/preamble.md` Steps 3–4 (CLI invocation, MCP detection) and Step 7 (operation routing, MCP-absent template, error rules).

This stub will be removed in a future plugin release. Do not link to it.
```

- [ ] **Step 3: Replace `conventions.md` with a stub**

Overwrite `skills/bigeye/references/conventions.md` with exactly:

```markdown
# BigEye Plugin — Conventions (moved)

Formatting rules (status/priority mapping, severity, scope pill, Brief/Full, footer, error blocks, tag conventions) moved to `skills/bigeye/references/output.md`.

User-editable configuration (Slack channel, severity thresholds, deploy defaults) moved to `~/.claude/bigeye-plugin/settings.json`. Manage via `/bigeye-config settings show` / `settings edit <key> <value>`.

This stub will be removed in a future plugin release. Do not link to it.
```

- [ ] **Step 4: Verify**

```bash
wc -l skills/bigeye/references/scope.md skills/bigeye/references/cli.md skills/bigeye/references/conventions.md
```

Expected: each file ≤ 8 lines.

- [ ] **Step 5: Stage**

```bash
git add skills/bigeye/references/scope.md skills/bigeye/references/cli.md skills/bigeye/references/conventions.md
```

---

## Task 5: (intentionally absent — folded into Task 1)

State-file schema and append-and-prune helper text live in `preamble.md` Step 8, written in Task 1. Skip this number to keep task numbering stable across the rollout.

---

## Task 6: Rewrite `bigeye-triage` SKILL.md

**Files:**
- Modify (rewrite): `skills/bigeye-triage/SKILL.md`

**Context:** Atomic skill rewrite. Behavior preserved. Three changes only: (1) preamble line points at `preamble.md`/`output.md` instead of the three old refs; (2) output adopts the scope pill, Brief default, `Next:`/`More:` footer, `Error / Fix / Why` block; (3) on success, append a `last_seen` update for every listed issue (no `actions[]` write — triage is a read).

The CLI fetch + filter + cluster-detect logic is unchanged from today's `skills/bigeye-triage/SKILL.md`.

- [ ] **Step 1: Overwrite the file**

Replace the entire contents of `skills/bigeye-triage/SKILL.md` with:

````markdown
---
name: bigeye-triage
description: Use when the user wants to see active BigEye issues, asks what's broken or on fire, or needs a prioritized view of data quality problems
user-invocable: true
---

# BigEye Triage

What it does: fetches all active issues, applies the active scope, and renders a prioritized table of New / Ack'd / Monitoring issues. Atomic — no menus. Building block called by `/bigeye-today`.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`.

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| (no arg) | All open issues (NEW + ACKNOWLEDGED + MONITORING) | `/bigeye-triage` |
| `new` | Only NEW status issues | `/bigeye-triage new` |
| `24h` | Issues opened in the last 24 hours | `/bigeye-triage 24h` |
| `<integer>` | Override `triage.max_issues` | `/bigeye-triage 100` |

Global flags (`--profile`, `--no-scope`, `--workspace`, `--full`, `--limit`, `--verbose`) — see `output.md`.

## Procedure

1. Follow `preamble.md` Steps 1–7. Read `settings.json.triage.max_issues` and `triage.default_brief_rows`.

2. Fetch open issues via CLI:
   ```bash
   TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
   trap 'rm -rf "$TMPDIR"' EXIT
   bigeye -w <profile> issues get-issues \
     {-wid <id> per data_source_id} \
     {-sn <name> per schema_name} \
     -op "$TMPDIR"
   ```
   Parse every JSON file in `$TMPDIR`. Filter:
   - Status in `{NEW, ACKNOWLEDGED, MONITORING}`. With `new` arg → `NEW` only. With `24h` arg → `openedAt` within 24 hours.
   - Table filter: build `effective_table_ids = union(profile.table_ids, resolved(profile.table_names))`. If non-empty, keep only issues whose `metricMetadata.datasetId` is in that set. (CLI has no table flag — this filter is post-fetch.)
   - Cap at `max_issues` (default 50, or the integer argument if given).

   If the filtered list is empty, print the empty-result line per `output.md` and stop after the footer.

   When MCP is unavailable and `table_names` couldn't resolve to IDs, print one warning line listing unresolved names; fall back to `effective_table_ids = profile.table_ids` alone.

3. Cluster detection:
   - `MCP_AVAILABLE=true`: for each open issue, call `mcp__bigeye__list_related_issues` with `starting_issue_id`. Count related issues per issue. Flag any with 2+ related as a cluster.
   - `MCP_AVAILABLE=false`: emit the MCP-absent warning per `preamble.md` Step 7.B with `feature_name=cluster detection`. Set `cluster_count=null`.

4. Render output. Group by `currentStatus` — one section per bucket (New / Ack'd / Monitoring). Sort rows within each bucket by `priorityScore` desc.

   Brief default: top `default_brief_rows` (10) per bucket. `--full` shows all. `--limit N` overrides count.

   ```
   {scope pill}
   ## BigEye Triage — {today's date}

   ### New ({count})
    # | Issue | Score | Dim | Table | Column | Since | History
    1 | 10921 |  87   | Freshness | orders | — | 2h | rca (4d)
    ...
   (<N more> — add --full to see all)

   ### Ack'd ({count})
    # | Issue | Score | Dim | Table | Column | Since | History
    ...

   ### Monitoring ({count})
    # | Issue | Score | Dim | Table | Column | Since | History
    ...

   Summary: {new_count} new · {ackd_count} ack'd · {monitoring_count} monitoring · {cluster_count} clusters
   ```

   `History` is sourced from `state.json.issues[<display_name>].actions` — last 2 distinct skill names + age (`rca (4d)`). Empty → `—`.

   If `cluster_count == null`, render `cluster detection: unavailable` instead.

   Status order is always New → Ack'd → Monitoring. Empty sections are omitted.

5. Footer:
   ```
   Next: /bigeye-rca {top-scored display_name}     (top-scored, not yet investigated)
   More: /bigeye-today  ·  /bigeye-incidents auto  ·  /bigeye  (dashboard)
   ```
   If clusters exist: replace the `Next:` value with `Next: /bigeye-incidents auto     ({cluster_count} clusters detected)`.

## State persistence

On successful render, follow `preamble.md` Step 8.B for the `bigeye-triage` row: update `state.json.issues[<display_name>].last_seen` and `status_when_last_seen` for every listed issue. Do **not** append to `actions[]`. Do not change `last_issue` or `last_table`.

Then run pruning per Step 8.C.

## Errors

CLI / scope / parse errors: per `preamble.md` Step 7.D. No skill-specific error paths.
````

- [ ] **Step 2: Verify**

```bash
grep -c "^## " skills/bigeye-triage/SKILL.md
grep -c "preamble.md\|output.md" skills/bigeye-triage/SKILL.md
grep -c "conventions.md\|scope.md\|cli.md" skills/bigeye-triage/SKILL.md
```

Expected: 5 sections (Arguments, Procedure, State persistence, Errors, plus the H1 — note `^## ` matches H2). Also: at least 3 references to `preamble.md`/`output.md`. Zero references to `conventions.md`/`scope.md`/`cli.md`.

- [ ] **Step 3: Stage**

```bash
git add skills/bigeye-triage/SKILL.md
```

---

## Task 7: Rewrite `bigeye-rca` SKILL.md

**Files:**
- Modify (rewrite): `skills/bigeye-rca/SKILL.md`

**Context:** Same shape as triage. New behaviors:
- No-arg form reads `state.json.last_issue` instead of auto-selecting from a fresh CLI dump.
- On success, write to state.json: `last_issue`, append `actions[]`.
- Out-of-scope soft notice now lives in `preamble.md` Step 5 — RCA references it.

- [ ] **Step 1: Overwrite the file**

Replace the entire contents of `skills/bigeye-rca/SKILL.md` with:

````markdown
---
name: bigeye-rca
description: Use when the user wants to investigate why a BigEye issue is happening, trace root causes through lineage, or debug a specific data quality problem
user-invocable: true
---

# BigEye Root Cause Analysis

What it does: traces an issue through data lineage to find the upstream root cause, related issues, and resolution steps. Atomic. No-arg form picks up from `state.json.last_issue`.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`.

Per `preamble.md` Step 5: primary issue lookup is **unscoped**. Scope applies only to lineage expansion and related-issue filtering. Out-of-scope soft notice rules also live in Step 5.

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `<display_name>` | Investigate a specific issue (e.g., `10921`) | `/bigeye-rca 10921` |
| (no arg) | Resume the last investigated issue from `state.json.last_issue`; if empty, ask | `/bigeye-rca` |
| `<internal_id> --internal-id` | Bypass MCP display-name lookup | `/bigeye-rca 42 --internal-id` |

Global flags — see `output.md`.

## Procedure

1. Follow `preamble.md` Steps 1–7.

2. Resolve the issue:
   - With `--internal-id`: treat the numeric arg as `internal_id` directly.
   - With no arg:
     - If `state.json.last_issue` is set: use it as the display name. Print one line: `Resuming issue {display_name} from previous session.`
     - Else: ask the user `Which issue? (display name)` and stop until they answer.
   - Otherwise the arg is a display name → resolve via MCP `search_issues`. If `MCP_AVAILABLE=false`, hard-fail per `preamble.md` Step 7.B with `feature_name=display-name lookup` and a Fix line `/bigeye-rca <internal-id> --internal-id`.

   On out-of-scope hit, print the soft notice per `preamble.md` Step 5 immediately after the scope pill.

3. Fetch issue details via CLI:
   ```bash
   TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
   trap 'rm -rf "$TMPDIR"' EXIT
   bigeye -w <profile> issues get-issues -iid <internal_id> -op "$TMPDIR"
   ```
   Read the single JSON. Note: metric type, table, column, opened_at, status, events history.

4. Lineage trace (MCP):
   - `MCP_AVAILABLE=true`: call `mcp__bigeye__get_issue_lineage_trace` with `issue_id`, `include_root_cause_analysis: true`, `include_impact_analysis: true`, `max_depth: 5`. Plus non-empty scope parameters from preamble Step 1.E if the tool's schema accepts them; otherwise post-filter.
   - `MCP_AVAILABLE=false`: emit MCP-absent warning per Step 7.B with `feature_name=lineage trace`. Skip this step.

5. Related issues (MCP):
   - `MCP_AVAILABLE=true`: `mcp__bigeye__list_related_issues` with `starting_issue_id`. Filter to in-scope tables/sources unless `--no-scope`. Note `isRootCause: true` rows.
   - `MCP_AVAILABLE=false`: emit the warning. Skip.

6. Resolution steps (MCP):
   - `MCP_AVAILABLE=true`: `mcp__bigeye__get_resolution_steps` with `issue_id`.
   - `MCP_AVAILABLE=false`: emit the warning. Skip.

7. Render output:
   ```
   {scope pill}
   {soft notice if applicable}
   {if any of steps 4–6 were skipped: a single line "Reduced RCA — MCP unavailable. Lineage, related issues, and/or resolution steps omitted. See bigeye-mcp-install.md."}

   ## Root Cause Analysis — Issue #{display_name}

   ### Issue
   {metric_type} failed on {schema}.{table}
   Column: {column or "table-level"}
   Status: {status_display} | Since: {time_since} | Priority: {priority_display}

   ### Lineage Trace
   {upstream_node_1} -> ... -> {issue_table}
   {Highlight any node flagged as ROOT CAUSE.}

   ### Related Issues
   | Issue | Dimension | Table | Root Cause? |
   |---|---|---|---|
   | ... | ... | ... | yes/no |

   ### Resolution Steps
   {numbered list from get_resolution_steps}

   ### Suggested Actions
   - {If 2+ related: "Group into incident: /bigeye-incidents <ids>"}
   - Acknowledge or close: /bigeye-incidents close {display_name} --label <label>
   - {If root cause is upstream: "Investigate upstream: /bigeye-rca <root_cause_display>"}
   ```

   For any MCP step skipped, replace its body with `(skipped — MCP unavailable)`.

8. Footer:
   ```
   Next: /bigeye-incidents {related_ids}     ({count} related — same root cause)
   More: /bigeye-ticket {display_name}  ·  /bigeye-incidents close {display_name}  ·  /bigeye-today
   ```
   If no related issues found, replace `Next:` with `Next: /bigeye-incidents close {display_name} --label true-negative     (resolved or expected)`.

## State persistence

On successful render, follow `preamble.md` Step 8.B for the `bigeye-rca` row:
- Set `state.json.last_issue = "<display_name>"`.
- If the table is known, set `state.json.last_table = "<schema.table>"`.
- Append `{ skill: "bigeye-rca", at: <iso8601-now> }` to `state.json.issues[<display_name>].actions`.
- Update `internal_id`, `first_seen` (if absent), `last_seen`, `status_when_last_seen`.
- Update `state.json.tables[<fq>].last_seen` and `actions[]` similarly.

Then run pruning per Step 8.C.

## Errors

| Condition | Block |
|---|---|
| Display-name unresolved (MCP) | `Error: BigEye returned no match for issue '<display_name>'.` / `Fix: re-check the number in the BigEye UI URL.` / `Why: search_issues returned 0 hits.` |
| MCP unavailable + display-name arg + no `--internal-id` | per Step 7.B with the workaround line |
| CLI / parse / scope errors | per Step 7.D |
````

- [ ] **Step 2: Verify**

```bash
grep -c "preamble.md" skills/bigeye-rca/SKILL.md
grep -c "state.json.last_issue\|state.json.issues" skills/bigeye-rca/SKILL.md
grep -c "conventions.md\|scope.md\|cli.md" skills/bigeye-rca/SKILL.md
```

Expected: at least 3 mentions of `preamble.md`; at least 2 mentions of state writes; zero mentions of the old refs.

- [ ] **Step 3: Stage**

```bash
git add skills/bigeye-rca/SKILL.md
```

---

## Task 8: Rewrite `bigeye-coverage` SKILL.md

**Files:**
- Modify (rewrite): `skills/bigeye-coverage/SKILL.md`

**Context:** Same template. New behaviors:
- No-arg form reads `state.json.last_table`. If empty, fall back to scope-driven enumeration (existing behavior).
- On success, set `last_table` and append to `tables[fq].actions`.

Existing logic (Step 4b weak-monitor scan, dimension coverage call, prioritized gap list, deploy hints) is preserved.

- [ ] **Step 1: Overwrite the file**

Replace the entire contents of `skills/bigeye-coverage/SKILL.md` with:

````markdown
---
name: bigeye-coverage
description: Use when the user wants to find monitoring gaps, check which columns or dimensions lack monitors, or assess overall monitoring coverage on their table
user-invocable: true
---

# BigEye Coverage Analysis

What it does: scores dimension coverage on a table (or the in-scope tables), prioritizes gaps using past issue history, and surfaces cheap weak-monitor findings inline.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`.

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `<table>` | Run coverage on a named table (bare, `schema.table`, or `source.schema.table`) | `/bigeye-coverage orders` |
| (no arg) | Use `state.json.last_table`. If empty, run on every in-scope table from the active profile. | `/bigeye-coverage` |
| `columns <c1>,<c2>` | Coverage limited to specific columns | `/bigeye-coverage columns email,phone` |
| `dimension <name>` | Filter gap list by dimension | `/bigeye-coverage dimension validity` |

Global flags — see `output.md`.

## Procedure

1. Follow `preamble.md` Steps 1–7.

2. Resolve the target tables:
   - Argument given → use it (single table). If a bare name needs MCP resolution and MCP is off, hard-fail with `feature_name=table-name resolution` and a Fix `/bigeye-coverage <source>.<schema>.<table>`.
   - No argument:
     - If `state.json.last_table` is set: use it. Print one line: `Coverage on {fq} (last table from prior session).`
     - Else: enumerate in-scope tables from the active profile (`table_ids` + resolved `table_names`). If none, fall back to `data_source_ids` and ask the user which table when more than one matches. Empty profile under `--no-scope` → ask.

3. For each target table, get dimension coverage (MCP):
   - `MCP_AVAILABLE=false`: per Step 7.B emit the warning with `feature_name=dimension coverage scoring` and a Fix line `Coverage scoring has no CLI equivalent — see bigeye-mcp-install.md.` Hard-stop.
   - `MCP_AVAILABLE=true`: `mcp__bigeye__get_table_dimension_coverage` with `table_name`. Capture overall %, per-dimension status, suggested metrics.

4. Get dimension taxonomy: `mcp__bigeye__list_dimensions` (categories: PIPELINE_RELIABILITY vs DATA_QUALITY).

5. If `columns <list>` was given: `mcp__bigeye__get_column_dimension_coverage` for those columns.

6. Fetch past issues via CLI:
   ```bash
   TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
   trap 'rm -rf "$TMPDIR"' EXIT
   bigeye -w <profile> issues get-issues {-wid <id>} {-sn <name>} -op "$TMPDIR"
   ```
   Parse JSON; filter to issues with `tableName == target_table`; keep `NEW`, `ACKNOWLEDGED`, `CLOSED` (last 30 days). Build the per-column issue counts.

7. Prioritize gaps:
   - **HIGH**: column has issues in last 30d AND missing dimensions
   - **MEDIUM**: no recent issues but missing critical dimensions (Freshness, Volume, Uniqueness, Completeness)
   - **LOW**: missing only non-critical dimensions (Distribution, Format)

   `dimension <name>` arg → filter the gap list to that dimension.

8. Cheap weak-monitor scan: apply heuristics from `skills/bigeye/references/improve.md` §2 with `Cheap? = yes` (REGEX_PERMISSIVE, LOOKBACK_MISSING, SCHEDULE_MISSING, HIGH_FALSE_POSITIVE_RATE) using monitor data already in hand from Step 3 + issue history from Step 6. Collect into `improvable_count` and a list of `(metric_id, column, one-sentence reason)`. No additional fetches.

9. Render:
   ```
   {scope pill}
   ## Coverage Report — {schema}.{table_name}

   ### Overall Score: {percent}% ({covered} of {total} dimension-column pairs covered)

   ### Table-Level Coverage
   | Dimension | Category | Status | Monitor |
   |---|---|---|---|
   | Freshness | Pipeline Reliability | Covered/GAP | {metric_name or —} |
   | ... | ... | ... | ... |

   ### Top Column Gaps (prioritized)
   | Column | Missing Dimensions | Past Issues (30d) | Priority |
   |---|---|---|---|
   | {col} | {dims} | {count} | HIGH |

   {Top 20 columns under Brief; --full shows all. "(N more — add --full to see all)" if truncated.}

   ### Improvable Monitors ({improvable_count})
   {only print if improvable_count > 0; up to 5 lines}
   - Metric #{id} on {column or "table-level"}: {reason}
   ... and {improvable_count - 5} more.

   ### Suggested Monitor Deployment
   {count} monitors recommended:
   - {N} {Dimension} monitors ({columns})
   - ...
   ```

10. Footer:
    ```
    Next: /bigeye-deploy gaps --priority high     ({high_count} high-priority gaps)
    More: /bigeye-improve {table}  ·  /bigeye-deploy gaps  ·  /bigeye-table {table}
    ```
    If `improvable_count > 0`: change `Next:` to `Next: /bigeye-improve {table}     ({improvable_count} weak monitors)`.

## State persistence

On successful render, follow `preamble.md` Step 8.B for the `bigeye-coverage` row:
- Set `state.json.last_table = "<schema.table>"` (or the fully-qualified target).
- Append `{ skill: "bigeye-coverage", at: <iso8601> }` to `state.json.tables[<fq>].actions`.
- Update `first_seen` (if absent) and `last_seen`.

Then run pruning per Step 8.C.

## Errors

CLI / scope / parse errors per `preamble.md` Step 7.D.
MCP-absent: per Step 7.B as documented in Step 3 above.
````

- [ ] **Step 2: Verify**

```bash
grep -c "preamble.md" skills/bigeye-coverage/SKILL.md
grep -c "state.json.last_table\|state.json.tables" skills/bigeye-coverage/SKILL.md
grep -c "conventions.md\|scope.md\|cli.md" skills/bigeye-coverage/SKILL.md
```

Expected: at least 3 / 2 / 0 respectively.

- [ ] **Step 3: Stage**

```bash
git add skills/bigeye-coverage/SKILL.md
```

---

## Task 9: Rewrite `bigeye-improve` SKILL.md

**Files:**
- Modify (rewrite): `skills/bigeye-improve/SKILL.md`

**Context:** Same template. New behaviors:
- No-arg form reads `state.json.last_table`. Empty → ask.
- On success, set `last_table` + append `actions[]`.
- Heavy-mode SQL paste protocol unchanged in behavior (still references `improve.md` §3–§4).

Existing 6-step procedure (weak monitors → coverage → profile refinement → primary report → SQL bundle → refined recommendations) is preserved.

- [ ] **Step 1: Overwrite the file**

Replace the entire contents of `skills/bigeye-improve/SKILL.md` with:

````markdown
---
name: bigeye-improve
description: Use when the user wants to improve BigEye monitors on a table — tighten weak regexes, recommend better thresholds, or suggest new monitors grounded in column profile data. Read-only — output is markdown; deploy is a separate /bigeye-deploy invocation.
user-invocable: true
---

# BigEye Monitor Improvement

What it does: scores existing monitors against quality heuristics, suggests missing-coverage monitor drafts, and (in heavy mode) emits warehouse SQL for the user to run, then refines recommendations from pasted results. Read-only — no writes.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`. Heuristics, SQL templates, and paste-parsing rules live in `skills/bigeye/references/improve.md`.

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `<table>` | Analyze the named table; heavy-mode by default | `/bigeye-improve orders` |
| (no arg) | Use `state.json.last_table`; if empty, ask | `/bigeye-improve` |
| `metric <metric_id>` | Single-metric deep analysis | `/bigeye-improve metric 17321` |
| `--light` | Skip heavy-mode SQL loop (Steps 5–6) | `/bigeye-improve orders --light` |
| `--sql-only` | Emit SQL bundle then stop (no paste-back) | `/bigeye-improve orders --sql-only` |
| `--dimension <name>` | Limit coverage suggestions to one dimension | `/bigeye-improve orders --dimension validity` |

Global flags — see `output.md`.

## Procedure

1. Follow `preamble.md` Steps 1–7. Per Step 5, the user-named table is **unscoped** — scope applies only to MCP calls that accept filters.

2. Resolve the target table:
   - Argument given → use it (ambiguous bare name → ask).
   - No argument:
     - `state.json.last_table` set → use it. Print: `Improving {fq} (last table from prior session).`
     - Else if profile resolves to exactly one table → use it (tell the user).
     - Else → ask which table to analyze. Never loop over all tables in a single heavy-mode run.

3. **Existing monitors (always runs):**
   ```bash
   TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
   trap 'rm -rf "$TMPDIR"' EXIT
   bigeye -w <profile> catalog get-metric-info -tid <table_id> -op "$TMPDIR"
   ```
   For each metric JSON, score against **all** heuristics in `improve.md` §2. For `HIGH_FALSE_POSITIVE_RATE`, fetch issue history:
   ```bash
   bigeye -w <profile> issues get-issues -sn <schema> -op "$TMPDIR/issues"
   ```
   Filter to `status=CLOSED`, `label=FALSE_POSITIVE`, `tableName=<table>`, `openedAt` within 30 days. Count per `metric_id`.

   Build `weak_monitors` = `[(metric_id, column, heuristic_id, severity, suggestion_text), ...]`.

4. **Missing coverage (MCP-only):**
   - `MCP_AVAILABLE=false`: per Step 7.B with `feature_name=missing-coverage suggestions`. Skip; set `coverage_suggestions = []`.
   - `MCP_AVAILABLE=true`: `get_table_dimension_coverage` + `get_column_dimension_coverage` for the table. For each gap, draft `(column, dimension, suggested_metric_type, parameters, rationale)`. With `--dimension`, filter to that dimension.

5. **Profile-based refinement (MCP-only):**
   - `MCP_AVAILABLE=false`: skip. Annotate every row in `weak_monitors` and `coverage_suggestions` that would benefit from profile data with `(profile unavailable)` in the rationale.
   - `MCP_AVAILABLE=true`: for each touched column, `mcp__bigeye__get_table_profile` with `table_name`, `columns`. Refine per `improve.md` §2 rules (null rate, distinct count, regex match rate against sample values).

6. **Emit primary report:**
   ```
   {scope pill}
   ## Monitor Improvement Report — {schema}.{table_name}

   ### Weak Monitors ({count})
   | Metric ID | Column | Why | Suggested change |
   |---|---|---|---|
   | ... | ... | ... | ... |

   ### Coverage Suggestions ({count})
   | Column | Missing dimension | Suggested metric | Rationale |
   |---|---|---|---|

   ### Deploy hints
   - /bigeye-deploy columns {col} --metric-type {TYPE}
   - /bigeye-deploy freshness
   - ...
   ```
   Sections with 0 rows are omitted. If both are empty, print `No improvements found — all monitors look healthy relative to current heuristics and {MCP on: "profile data" / MCP off: "available configuration data"}.` then footer + state-write + exit (skip Steps 7–8).

7. **Heavy-mode SQL bundle (default; skipped by `--light`):**
   Identify columns still needing deeper reasoning (any `weak_monitors` row flagged `THRESHOLD_DEFAULT`/`METRIC_TYPE_MISMATCH`; any `coverage_suggestions` row whose params aren't final). Empty list → skip Steps 7–8.
   Otherwise, render the SQL bundle from `improve.md` §3 templates. Look up the warehouse dialect from CLI's `catalog get-table-info` (`warehouseType` field). Print numbered progress markers `[N/M]` per `output.md` §Progress indicators. Emit the bundle.
   With `--sql-only`: stop after the bundle. With heavy default: emit the paste protocol from `improve.md` §4.1 verbatim, then end the current turn.

8. **Refined recommendations (heavy mode only, triggered by paste):**
   On the next user message, parse per `improve.md` §4.2. Parse failure → ask for a re-paste of only failed `-- query N` blocks; preserve successful sections.
   `cancel` → produce a best-effort report from Steps 3–5 + the cancellation line per `improve.md` §4.3.
   Else: emit
   ```
   ## Refined Recommendations
   {one paragraph per refined suggestion, grouped by column}

   ### Deploy hints (updated)
   - /bigeye-deploy columns {col} --metric-type {TYPE}   <- refined threshold: {value}
   - ...
   ```

9. Footer (always — printed at the end of the **last** block emitted):
   ```
   Next: /bigeye-deploy columns {top_col} --metric-type {TYPE}     ({weak_count} weak monitors / {gap_count} gaps)
   More: /bigeye-coverage {table}  ·  /bigeye-table {table}  ·  /bigeye-deploy gaps
   ```

## State persistence

On the **last** successful render of the run (Step 6 for `--light`/`--sql-only`/empty result; Step 8 for heavy mode), follow `preamble.md` Step 8.B for the `bigeye-improve` row:
- Set `state.json.last_table = "<schema.table>"`.
- Append `{ skill: "bigeye-improve", at: <iso8601> }` to `state.json.tables[<fq>].actions`.
- Update `first_seen` / `last_seen`.

Then run pruning per Step 8.C.

## MCP-absent matrix

| Mode | MCP on | MCP off |
|---|---|---|
| `--light` | weak + coverage + profile | weak only; coverage skipped |
| default (heavy) | weak + coverage + profile + SQL + refined | weak + SQL + refined (no coverage, no profile) |
| `--sql-only` | weak + coverage + profile + SQL (stops) | weak + SQL (stops) |

Hard-fail only when CLI itself cannot reach the workspace (auth/network) — per `preamble.md` Step 7.D.

## Errors

| Condition | Behavior |
|---|---|
| Table not found | Print CLI error verbatim per Step 7.D; suggest `/bigeye-config show`; stop |
| No metrics on table AND MCP off | Print one line `Nothing to improve — no existing monitors and MCP unavailable, so no coverage data. See bigeye-mcp-install.md.`; clean exit |
| MCP profile fetch partial failure | Continue with successful columns; mark failed rows `(profile unavailable for this column)` |
| Heavy-mode paste parse failure | Report failed `-- query N` blocks; ask for re-paste of only those; preserve progress |
| User sends `cancel` mid heavy-mode | Best-effort report from Steps 3–5 + cancellation line per `improve.md` §4.3 |
| Unknown warehouse dialect for `DISTRIBUTION_BUCKETS` | Emit comment-only skip placeholder per `improve.md` §3; continue |
````

- [ ] **Step 2: Verify**

```bash
grep -c "preamble.md\|output.md" skills/bigeye-improve/SKILL.md
grep -c "state.json.last_table" skills/bigeye-improve/SKILL.md
grep -c "conventions.md\|scope.md\|cli.md" skills/bigeye-improve/SKILL.md
```

Expected: at least 3 / 2 / 0 respectively.

- [ ] **Step 3: Stage**

```bash
git add skills/bigeye-improve/SKILL.md
```

---

## Task 10: Rewrite `bigeye-deploy` SKILL.md

**Files:**
- Modify (rewrite): `skills/bigeye-deploy/SKILL.md`

**Context:** Same template. New behaviors:
- Defaults read from `settings.json.deploy.default_lookback_days` and `settings.json.deploy.tag` instead of being hardcoded.
- Confirmation gate text unchanged.
- On successful apply, append `{ skill: "bigeye-deploy", note: "<N monitors created>" }` to `tables[fq].actions` and set `last_table`.

Existing logic (gaps/bulk via bigconfig, freshness/columns via metric upsert, tagging) is preserved.

- [ ] **Step 1: Overwrite the file**

Replace the entire contents of `skills/bigeye-deploy/SKILL.md` with:

````markdown
---
name: bigeye-deploy
description: Use when the user wants to create monitors, deploy metrics, set up freshness checks, or close monitoring gaps identified by coverage analysis
user-invocable: true
---

# BigEye Monitor Deployment

What it does: bulk monitor creation with sensible defaults and a mandatory confirmation gate. Two paths: bigconfig (gaps/bulk) and imperative (freshness/columns).

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`.

<HARD-GATE>
NEVER create monitors without showing the deployment plan and receiving explicit user confirmation.
This is a write operation that creates real monitors in production BigEye.
</HARD-GATE>

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `gaps` | Deploy all suggestions from the most recent coverage analysis | `/bigeye-deploy gaps` |
| `gaps --priority high` | High-priority gaps only | `/bigeye-deploy gaps --priority high` |
| `gaps --priority medium` | Medium + high priority gaps | `/bigeye-deploy gaps --priority medium` |
| `columns <c1>,<c2>` | Deploy on specific columns; auto-suggest types | `/bigeye-deploy columns email` |
| `freshness` | Add a freshness monitor to the table | `/bigeye-deploy freshness` |
| `bulk <dimension>` | Apply a dimension across all unmonitored columns | `/bigeye-deploy bulk validity` |
| `--metric-type <TYPE>` | Required for `columns <list>` when MCP off; applies same type to all named columns | `/bigeye-deploy columns email --metric-type VALID_REGEX` |

Defaults applied (override via `/bigeye-config settings edit deploy.<key> <value>`):
- Lookback: `settings.json.deploy.default_lookback_days` (default 7).
- Tracking tag: `settings.json.deploy.tag` (default `deployed-by-plugin`).

Global flags — see `output.md`.

## Procedure

1. Follow `preamble.md` Steps 1–7. Read `settings.json.deploy.default_lookback_days` and `deploy.tag`.

2. Build the deployment plan.

   **For `gaps` / `bulk <dimension>`** (bigconfig path):
   - `MCP_AVAILABLE=false`: hard-fail per Step 7.B with `feature_name=coverage-driven deploy planning`.
   - `MCP_AVAILABLE=true`: per in-scope table, call `mcp__bigeye__get_table_dimension_coverage`. Filter by `--priority high|medium`. For `bulk <dimension>`, restrict to that dimension.
   - Build a bigconfig YAML at `$TMPDIR/bigconfig.yaml`:
     ```yaml
     type: BIGCONFIG_FILE
     tag_deployments:
       - collection:
           name: plugin-deployed
         deployments:
           - fq_table_name: <data_source>.<schema>.<table>
             columns:
               - column_name: <column>
                 metrics:
                   - saved_metric_id: <auto-named-id>
                     metric_type:
                       predefined_metric:
                         metric_name: <METRIC_TYPE>
                     lookback:
                       lookback_window: { interval_type: DAYS, interval_value: <default_lookback_days> }
                       lookback_type: DATA_TIME
     ```

   **For `columns <list>`** (imperative path):
   - `MCP_AVAILABLE=true` and no `--metric-type`: `mcp__bigeye__get_column_dimension_coverage` to infer per-column types.
   - `MCP_AVAILABLE=false` and no `--metric-type`: hard-fail per Step 7.B with `feature_name=per-column dimension inference` and Fix `Re-run with --metric-type <TYPE>`.
   - `--metric-type` given: skip inference, use that type for every column.
   - Build one `SimpleUpsertMetricRequest` YAML per column at `$TMPDIR/<column>.yaml`:
     ```yaml
     schema_name: <schema>
     table_name: <table>
     column_name: <column>
     metric_type: <METRIC_TYPE>
     lookback:
       lookback_window: { interval_type: DAYS, interval_value: <default_lookback_days> }
       lookback_type: DATA_TIME
     ```

   **For `freshness`** (imperative, no MCP needed): same template, table-level (no `column_name`), metric_type `FRESHNESS`.

3. Print numbered progress per `output.md` §Progress indicators (`[1/4] Building plan ...`).

4. Present the plan and WAIT for confirmation:
   ```
   {scope pill}
   ## Deploy Plan — {count} monitors on {table_name}

   | # | Column | Metric Type | Dimension | Lookback |
   |---|---|---|---|---|
   | 1 | {col or —} | {metric_type} | {dimension} | {default_lookback_days} days |
   | 2 | ... | ... | ... | ... |

   Defaults applied:
   - Lookback: {default_lookback_days} days (DATA_TIME)
   - Tracking tag: {deploy.tag}

   Proceed? (y/n/edit)
   - y    — create all monitors as shown
   - n    — cancel deployment
   - edit — describe changes (e.g., "remove row 3", "change lookback to 14 days for row 1")
   ```
   Show the exact CLI invocation that will run:
   - bigconfig: `bigeye -w <profile> bigconfig plan -ip $TMPDIR -op $TMPDIR/plan/` (then `apply -auto_approve` on confirm)
   - imperative: `bigeye -w <profile> metric upsert -f <file> -t SIMPLE` per file

   On `edit`, apply changes and re-present until `y` or `n`.

5. Ensure the tracking tag exists:
   - `MCP_AVAILABLE=false`: per Step 7.B with `feature_name=monitor tagging`. Set `SKIP_TAGGING=true`. Continue.
   - `MCP_AVAILABLE=true`: `mcp__bigeye__list_tags` with `search: <deploy.tag>`. If absent, `mcp__bigeye__create_tag` (`name: <deploy.tag>`, `color_hex: "#6366F1"`). Store `tag_id`.

6. Create monitors.

   **bigconfig path:**
   1. `bigeye -w <profile> bigconfig plan -ip "$TMPDIR" -op "$TMPDIR/plan"`.
   2. Read plan report. Print `Plan: N create, M update, 0 errors.`
   3. Re-confirm: `Apply now? (y/n)`. On `n`, stop without writes.
   4. `bigeye -w <profile> bigconfig apply -ip "$TMPDIR" -auto_approve`.
   5. Read apply report. Extract created metric IDs.

   **imperative path:** for each YAML in `$TMPDIR`, run `bigeye -w <profile> metric upsert -f <file_path> -t SIMPLE`. Track success/failure. Parse output for created metric IDs.

7. Tag created monitors (skip if `SKIP_TAGGING=true`):
   For each successfully created monitor, `mcp__bigeye__tag_entity` with `tag_id`, `entity_id: <metric_id>`, `entity_type: METRIC`.

8. Render results:
   ```
   ## Deployment Results

   {success}/{total} monitors created successfully

   {if failures:}
   Failed:
   - {metric_type} on {column}: {error}

   Created monitor IDs: {ids}
   All monitors tagged with `{deploy.tag}` for tracking.
   {if SKIP_TAGGING: "Note: monitors were NOT tagged (MCP unavailable). Re-run after enabling MCP to backfill tags."}
   ```

9. Footer:
   ```
   Next: /bigeye-triage     (verify in ~1 hour)
   More: /bigeye-coverage {table}  ·  /bigeye-table {table}  ·  /bigeye-improve {table}
   ```

## State persistence

On successful apply (Step 6 success), follow `preamble.md` Step 8.B for the `bigeye-deploy` row:
- Set `state.json.last_table = "<fq>"` (when target was a table).
- Append `{ skill: "bigeye-deploy", at: <iso8601>, note: "<N monitors created>" }` to `state.json.tables[<fq>].actions`.
- Update `first_seen` / `last_seen`.

Then run pruning per Step 8.C. Failed deploys do not write state.

## Errors

| Condition | Behavior |
|---|---|
| MCP off + `gaps`/`bulk` | hard-fail per Step 7.B (no CLI equivalent for coverage) |
| MCP off + `columns` w/o `--metric-type` | hard-fail per Step 7.B with workaround |
| bigconfig plan errors | print plan errors verbatim; do not proceed to apply |
| imperative upsert partial failure | report success/fail counts; do not chain Next-action until fixed |
| Tag creation failure | continue; print warning; do NOT skip the monitor create |
````

- [ ] **Step 2: Verify**

```bash
grep -c "preamble.md\|output.md" skills/bigeye-deploy/SKILL.md
grep -c "settings.json.deploy\|deploy.default_lookback_days\|deploy.tag" skills/bigeye-deploy/SKILL.md
grep -c "conventions.md\|scope.md\|cli.md" skills/bigeye-deploy/SKILL.md
grep -c "<HARD-GATE>" skills/bigeye-deploy/SKILL.md
```

Expected: at least 3 / 3 / 0 / 1.

- [ ] **Step 3: Stage**

```bash
git add skills/bigeye-deploy/SKILL.md
```

---

## Task 11: Rewrite `bigeye-incidents` SKILL.md

**Files:**
- Modify (rewrite): `skills/bigeye-incidents/SKILL.md`

**Context:** Same template. New behaviors:
- On successful merge/create, set `last_issue` (last grouped issue), append `{ skill: "bigeye-incidents", note: "grouped with <list>" }` to `issues[<id>].actions` for each merged issue.

Existing modes (Merge / auto / Add / Close) preserved.

- [ ] **Step 1: Overwrite the file**

Replace the entire contents of `skills/bigeye-incidents/SKILL.md` with:

````markdown
---
name: bigeye-incidents
description: Use when the user wants to group related BigEye issues into incidents, merge issues, manage existing incidents, or auto-detect issue clusters
user-invocable: true
---

# BigEye Incident Management

What it does: groups related issues into incidents, manages existing incidents, and auto-detects clusters from open issues.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`.

<HARD-GATE>
NEVER create or modify incidents without showing the plan and receiving explicit user confirmation.
Incidents affect issue visibility and tracking in the BigEye UI for the entire team.
</HARD-GATE>

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `<id1> <id2> ...` | Merge specific display names into a new incident | `/bigeye-incidents 10921 10922 10923` |
| `auto` | Auto-detect clusters from open issues; suggest groupings | `/bigeye-incidents auto` |
| `add <id> to <incident_id>` | Add an issue to an existing incident | `/bigeye-incidents add 10925 to 482` |
| `close <id> --label <label>` | Close an issue with a closing label (`true-negative` / `false-positive` / `expected`) | `/bigeye-incidents close 10921 --label expected` |
| `--internal-id` | Treat all numeric arguments as internal IDs (required when MCP unavailable) | |

Global flags — see `output.md`.

## Procedure

Per `preamble.md` Step 5: scope filters `auto` candidates and the `list_issues` call. Explicit-ID modes honor user IDs unconditionally.

### Mode: Merge specific issues (`<id1> <id2> ...`)

1. Resolve display names → internal IDs:
   - `--internal-id`: numbers are internal IDs.
   - else `MCP_AVAILABLE=true`: `mcp__bigeye__search_issues` per name.
   - else `MCP_AVAILABLE=false`: hard-fail per Step 7.B (`feature_name=display-name lookup`, Fix `Re-run with --internal-id`).
   At least 2 IDs required.

2. Validate relationship:
   - `MCP_AVAILABLE=true`: `mcp__bigeye__list_related_issues` for the first ID; check that the others appear. If not, warn `These issues don't appear to be related through data lineage. Proceed anyway? (y/n)`.
   - `MCP_AVAILABLE=false`: skip validation; emit Step 7.B note (`feature_name=relationship validation`).

3. Generate incident name from the issues (root cause, dimension, table). Format: `{dimension} issue affecting {table}` or `{root_cause_dimension} cascade from {source_table}`.

4. Present plan + confirm:
   ```
   {scope pill}
   ## Create Incident — "{generated_name}"

   Issues to merge:
   | Issue | Dimension | Table | Column | Status | Root Cause? |
   |---|---|---|---|---|---|
   | ... | ... | ... | ... | ... | yes/no |

   Proceed? (y/n/edit name)
   ```
   Wait for confirmation.

5. Create:
   - `MCP_AVAILABLE=false`: hard-fail per Step 7.B (`feature_name=incident creation`, no CLI equivalent).
   - else: `mcp__bigeye__create_incident` with `issue_ids` and `incident_name`.

6. Render result:
   ```
   ## Incident Created — "{name}"

   Issues merged:
   - #{display_1} (root cause) — {description}
   - #{display_2} — {description}

   Root cause: #{root_cause_display}
   Downstream impact: {related_count} issues
   ```

7. Footer:
   ```
   Next: /bigeye-rca {root_cause_display}     (deep dive on the root cause)
   More: /bigeye-today  ·  /bigeye-triage  ·  /bigeye-incidents auto
   ```

### Mode: Auto-detect (`auto`)

1. Fetch open issues via CLI (same pattern as `bigeye-triage`); filter to `NEW + ACKNOWLEDGED`; cap at 50.

2. Build relationship graph:
   - `MCP_AVAILABLE=false`: hard-fail per Step 7.B (`feature_name=cluster auto-detection`).
   - else: `mcp__bigeye__list_related_issues` per issue. Cluster issues that share at least one related issue (transitive closure).

3. Present clusters:
   ```
   {scope pill}
   ## Auto-Detected Issue Clusters

   ### Cluster 1: "{auto_name}" ({count} issues)
   | Issue | Dimension | Table | Root Cause? |
   |---|---|---|---|

   ### Cluster 2: ...

   {count_unclustered} issues have no detected relationships (not shown).

   Create incidents for these clusters? (all/1,2/none)
   ```

4. For each confirmed cluster, run Steps 3–6 of the Merge mode above.

### Mode: Add to existing (`add <id> to <incident_id>`)

1. Resolve both IDs (display-name lookup per Merge Step 1).
2. `MCP_AVAILABLE=false`: hard-fail per Step 7.B.
3. `mcp__bigeye__create_incident` with `issue_ids: [<issue_id>]`, `existing_incident_id: <incident_internal_id>`.
4. Render result + footer.

### Mode: Close (`close <id> --label <label>`)

1. Resolve `<id>` (per above; MCP required for display-name).
2. Map `--label` per `output.md` §Closing labels: `true-negative` → `TRUE_POSITIVE`, `false-positive` → `FALSE_POSITIVE`, `expected` → `EXPECTED`.
3. ```bash
   bigeye -w <profile> issues update-issue -iid <internal_id> -status CLOSED -cl <mapped_label>
   ```
4. On success:
   ```
   {scope pill}
   Issue #{display} closed with label {mapped_label}.
   ```
5. Footer:
   ```
   Next: /bigeye-today     (continue triage)
   More: /bigeye-triage  ·  /bigeye  (dashboard)
   ```

## State persistence

On successful merge/create/close, follow `preamble.md` Step 8.B for the `bigeye-incidents` row:
- Set `state.json.last_issue` to the most recent issue touched (last in the merged list, or the closed one).
- For each issue touched, append `{ skill: "bigeye-incidents", at: <iso8601>, note: "grouped with <list>" }` (or `note: "closed with <label>"` for close mode) to `state.json.issues[<display>].actions`.
- For the close mode, also update `status_when_last_seen = "CLOSED"`.

Then run pruning per Step 8.C.

## Errors

| Condition | Behavior |
|---|---|
| Display-name unresolved | print MCP error verbatim per Step 7.D |
| MCP off + create/auto | hard-fail per Step 7.B |
| Update-issue CLI error | print stderr per Step 7.D; do not write state |
| Single ID for merge mode | print `Need at least 2 issue IDs to create a new incident.` and stop |
````

- [ ] **Step 2: Verify**

```bash
grep -c "preamble.md\|output.md" skills/bigeye-incidents/SKILL.md
grep -c "state.json.last_issue\|state.json.issues" skills/bigeye-incidents/SKILL.md
grep -c "<HARD-GATE>" skills/bigeye-incidents/SKILL.md
grep -c "conventions.md\|scope.md\|cli.md" skills/bigeye-incidents/SKILL.md
```

Expected: at least 3 / 2 / 1 / 0.

- [ ] **Step 3: Stage**

```bash
git add skills/bigeye-incidents/SKILL.md
```

---

## Task 12: Rewrite `bigeye-ticket` SKILL.md

**Files:**
- Modify (rewrite): `skills/bigeye-ticket/SKILL.md`

**Context:** Same template. New behaviors:
- On successful render, set `last_issue` and append `{ skill: "bigeye-ticket", at: <iso> }`.

Existing logic (templates wizard, render path, MCP-only variable substitution) preserved.

- [ ] **Step 1: Overwrite the file**

Replace the entire contents of `skills/bigeye-ticket/SKILL.md` with:

````markdown
---
name: bigeye-ticket
description: Use when the user wants to draft a vendor ticket, write a Service Request, or generate a markdown report for a data vendor about a BigEye issue. Render-only — no external ticketing system writes.
user-invocable: true
---

# BigEye Ticket Drafter

What it does: renders a markdown ticket draft from a BigEye issue using a user-authored template at `~/.claude/bigeye-plugin/ticket-templates/<name>.md`. Output is copy-pasteable markdown — the plugin never submits anywhere.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`. Template variable catalog lives in `skills/bigeye/references/improve.md` §1.

Per `preamble.md` Step 5, primary issue lookup is **unscoped** — scope applies only to MCP lineage/related calls.

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `<issue>` | Render the `default` template for the named issue | `/bigeye-ticket 10921` |
| (no arg) | Use `state.json.last_issue`; if empty, ask | `/bigeye-ticket` |
| `--template <name> <issue>` | Use a specific named template | `/bigeye-ticket --template oracle 10921` |
| `templates list` | Print name, modified-at, size for each template | |
| `templates add <name>` | Wizard: paste template body, validate, save | |
| `templates edit <name>` | Wizard: re-paste body; preserve until confirmed | |
| `templates delete <name>` | Confirm + remove file | |
| `--internal-id` | Treat the numeric argument as an internal ID (bypass MCP lookup) | |

Template-name validation: `^[a-zA-Z0-9_-]+$`. Reject `default` for `add` unless the user explicitly confirms overwrite.

Global flags — see `output.md`.

## Render path

1. Follow `preamble.md` Steps 1–7.

2. Seed templates directory on first run if `~/.claude/bigeye-plugin/ticket-templates/` is missing or empty:
   - Create the directory.
   - Copy the bundled `skills/bigeye-ticket/templates/default.md` to `~/.claude/bigeye-plugin/ticket-templates/default.md`.
   - Print: `Seeded default template. Run /bigeye-ticket templates edit default to customize, or /bigeye-ticket templates add <name> to add your own.`
   - Continue. If `--template <name>` names something other than `default`, stop with the template-not-found error.

3. Resolve the issue:
   - `--internal-id`: number is internal ID directly.
   - No arg + `state.json.last_issue` set: use it as display name. Print `Drafting for issue {display_name} (last from prior session).`
   - No arg + state empty: ask `Which issue?` and stop.
   - Display name → MCP `search_issues` (hard-fail per Step 7.B if MCP off, with workaround `Re-run with --internal-id <internal-id>`).

4. Fetch issue details via CLI:
   ```bash
   TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
   trap 'rm -rf "$TMPDIR"' EXIT
   bigeye -w <profile> issues get-issues -iid <internal_id> -op "$TMPDIR"
   ```
   Read the JSON. Extract all CLI-sourced variables per `improve.md` §1 (`MCP required? = no` rows).

5. Fetch MCP-only variables (best-effort). Track an `affected_vars` list. For each:
   - `{{downstream_tables}}` — if MCP on, `mcp__bigeye__get_issue_lineage_trace` (`include_impact_analysis: true`, `max_depth: 3`). Format as bullet list. On error / MCP off: substitute `_(unavailable — MCP not configured)_` and add to `affected_vars`.
   - `{{related_issues}}` — if MCP on, `mcp__bigeye__list_related_issues`. Format as bullet list. Else: substitute and add.
   - `{{resolution_steps}}` — if MCP on, `mcp__bigeye__get_resolution_steps`. Format as numbered list. Else: substitute and add.

   Apply preamble Step 1.E filtering to MCP calls (downstream/related items kept only when in scope; primary issue itself unscoped per Step 5).

6. Render `{{sample_query}}` per `improve.md` §1.1 from the metric type.

7. Load the template body from `~/.claude/bigeye-plugin/ticket-templates/<name>.md` (default if `--template` not given). On I/O error, follow §Errors below.

8. Single-pass `{{variable}}` substitution. Variables in `improve.md` §1 → resolved values. Unknown `{{...}}` → leave literal; collect into `unknown_vars`.

9. Emit output (in this exact order):
   1. `{scope pill}`
   2. blank line
   3. Triple-backtick fenced block containing the rendered ticket body.
   4. blank line
   5. If `affected_vars` non-empty: `Note: {comma-separated names} omitted — MCP not configured (see bigeye-mcp-install.md).`
   6. If `unknown_vars` non-empty: `Warning: template referenced unknown variables: {comma-separated names}`.
   7. blank line

10. Footer:
    ```
    Next: /bigeye-rca {display_name}     (investigate before sending the ticket)
    More: /bigeye-incidents close {display_name}  ·  /bigeye-today  ·  /bigeye-ticket templates list
    ```

## Wizard flow (`templates add` / `templates edit`)

Mirror `bigeye-config init`. Ask one question at a time; show the running summary.

1. Validate `<name>` against `^[a-zA-Z0-9_-]+$`. Reject otherwise: `Template name must match ^[a-zA-Z0-9_-]+$.`
2. `add` with `<name>=default`: ask `The bundled default template already exists. Overwrite it? (y/n)` — `n` stops.
3. If file exists (both modes): print size; ask `Overwrite? (y/n)` for `add`. For `edit`, just show current size.
4. Print short variable catalog from `improve.md` §1, grouped CLI-sourced / MCP-only.
5. `Paste your template. Finish with a single line containing only EOF.`
6. Read up to 200 lines. If no `EOF` after 200, ask `Paste exceeded 200 lines without EOF terminator. Restart the wizard? (y/n)` — `n` exits without writing.
7. Scan body for `{{...}}`; categorize "used" vs "unknown" against §1. Print `Uses: <list>. Unknown placeholders: <list or "none">.`
8. Prompt `Save? (y/n)` — `n` discards.
9. Write atomically (sibling tempfile + rename).
10. Print `Wrote ~/.claude/bigeye-plugin/ticket-templates/<name>.md.`

### `templates list`

Print one row per `*.md` file:
```
| Template | Modified | Size |
|---|---|---|
| {name} | {ISO-8601 mtime} | {bytes} |
```
Empty/missing dir: `No templates yet. Run /bigeye-ticket <issue> to seed the default.`

### `templates delete <name>`

1. Confirm file exists (else list available + stop).
2. Ask `Delete template <name>? (y/n)` — `n` stops.
3. Remove file. Print `Deleted ~/.claude/bigeye-plugin/ticket-templates/<name>.md.`

## State persistence

On successful render, follow `preamble.md` Step 8.B for the `bigeye-ticket` row:
- Set `state.json.last_issue = "<display_name>"`.
- Append `{ skill: "bigeye-ticket", at: <iso8601> }` to `state.json.issues[<display>].actions`.
- Update `internal_id`, `first_seen`, `last_seen`.

Wizard subcommands (`templates add/edit/delete/list`) do **not** write state.

Then run pruning per Step 8.C.

## Errors

| Condition | Behavior |
|---|---|
| Issue not found | print error per Step 7.D; suggest checking display name |
| Template file not found | list available; suggest `/bigeye-ticket templates add <name>` |
| Template I/O error | print OS error + absolute path; do not delete |
| Unknown `{{variable}}` | leave literal; append warning per Step 9.6 |
| MCP-only variable fetch failed / MCP down | substitute `_(unavailable — MCP not configured)_`; add to `affected_vars` for footer |
| Wizard paste exceeds 200 lines | per wizard Step 6 |
| Wizard `n` confirm | discard without disk touches |
````

- [ ] **Step 2: Verify**

```bash
grep -c "preamble.md\|output.md" skills/bigeye-ticket/SKILL.md
grep -c "state.json.last_issue\|state.json.issues" skills/bigeye-ticket/SKILL.md
grep -c "conventions.md\|scope.md\|cli.md" skills/bigeye-ticket/SKILL.md
```

Expected: at least 3 / 2 / 0.

- [ ] **Step 3: Stage**

```bash
git add skills/bigeye-ticket/SKILL.md
```

---

## Task 13: Rewrite `bigeye/SKILL.md` as the dashboard

**Files:**
- Modify (rewrite): `skills/bigeye/SKILL.md`

**Context:** `/bigeye` was an intent router. After redesign, it becomes a non-interactive dashboard. Free-text trailing args print a `Did you mean …?` hint above the dashboard but DO NOT route — routing is gone. Sections render in the order the spec gives.

The dashboard reads issue data once (filtered by active scope) and reuses that for both the "Open issues" table and the "Your tables" open-counts column.

- [ ] **Step 1: Overwrite the file**

Replace the entire contents of `skills/bigeye/SKILL.md` with:

````markdown
---
name: bigeye
description: Use when the user mentions BigEye, data quality issues, monitoring gaps, data freshness, monitor coverage, issue triage, root cause analysis, or wants a snapshot of the current state of their BigEye scope. Renders the dashboard.
user-invocable: true
---

# BigEye Dashboard

What it does: one-pass, non-interactive snapshot of the active scope — current issues, recent activity from local state, per-table coverage and open counts, and a stable command cheatsheet. No menus. No prompts. Footer points at the workflow command that does the most work for the user right now.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`.

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| (no arg) | Render the dashboard for the active profile | `/bigeye` |
| `--all` | Ignore scope filters for the issues + tables sections; expand state.json view | `/bigeye --all` |
| `<free text>` | Render the dashboard, prefixed by a `Did you mean /bigeye-<x>?` hint | `/bigeye triage` |

Global flags — see `output.md`.

## Procedure

1. Follow `preamble.md` Steps 1–7.

2. If trailing args are present and don't match a known flag, print exactly:
   ```
   Did you mean /bigeye-<x> <args>? /bigeye shows the dashboard; individual commands run tasks.
   ```
   Then continue rendering — do **not** route. The trailing args are otherwise ignored.

3. Read state.json (preamble Step 8.A). Hold `state.last_workflow`, `state.issues`, `state.tables`, `state.last_issue`, `state.last_table` for later sections.

4. Fetch open issues via CLI (same pattern as `bigeye-triage`; cap at `triage.max_issues`). Apply scope per preamble Step 5. With `--all`, skip the scope filter.

5. Cluster count:
   - MCP on: per-issue `list_related_issues`. Count groups of 2+. Hold as `cluster_count`.
   - MCP off: `cluster_count = "—"`.

6. Coverage average:
   - MCP on: for each in-scope table, `get_table_dimension_coverage`. Compute the average %. Hold individual values for the "Your tables" section.
   - MCP off: `coverage_avg = "—"`; per-table coverage = `—`.

7. Build the rendered output, in this order:

   ```
   {scope pill}
   ## BigEye Dashboard — {weekday} {month} {day}, {HH:MM}

   Status:  {open_count} open  ·  {new_count} NEW  ·  {cluster_count} clusters  ·  coverage {coverage_avg}%
   Last:    {short skill tag} {age ago}  ·  {next-most-recent skill tag} {age ago}
   ```

   - `Last:` reads from `state.last_workflow`/`state.last_issue`/`state.last_table` plus the most recent two `actions[]` entries across `state.issues` + `state.tables`. If `state.json` is empty: `Last: no activity yet — run /bigeye-today to get started`.

   ```
   Open issues (top 5 by score):
    # | Issue | Score | Dim       | Table    | Column | Since | History
    1 | 10921 |  87   | Freshness | orders   | —      | 2h    | rca (4d)
    ...
    (N more — run /bigeye-today for full picker)
   ```
   - Always exactly 5 rows when the underlying list has more (truncation marker line below the table). When fewer than 5, render only the rows you have, no marker.
   - `History` from `state.issues[<display>].actions` (last 2 distinct skills, age).

   ```
   Recently closed (last 7 days):
    - #10809 Freshness on orders (true-positive, 2d ago)
    - #10792 Validity on payments.email (false-positive, 4d ago)
   ```
   - Up to 5 lines. Sourced only from `state.json` entries whose `status_when_last_seen == "CLOSED"` and `last_seen` within 7 days. Section is omitted entirely if zero.

   ```
   Your tables:
    Table                              | Coverage | Open | Last action
    warehouse.public.orders            |  64%     |  3   | improve 3d ago
    ...
   ```
   - Iterate `profile.table_ids` + resolved `profile.table_names`. Per row: coverage % from Step 6; open count post-filtered from the issue list in Step 4; last action from `state.tables[<fq>].actions[-1]`.
   - If the profile has no table filters (only workspace + sources), substitute a `Top tables (by activity)` section: 5 most-recently-used tables from `state.tables` filtered by current scope.
   - If no table filters AND state.tables is empty, omit the section entirely.

   ```
   Commands:
    /bigeye-today                   reactive: triage -> act
    /bigeye-table <name>            proactive: audit a table
    /bigeye-rca [issue]             root cause a single issue
    /bigeye-coverage [table]        monitoring gaps
    /bigeye-improve [table]         tighten weak monitors
    /bigeye-deploy [target]         create monitors (confirmation)
    /bigeye-incidents [ids|auto]    group related issues
    /bigeye-ticket [issue]          render markdown ticket
    /bigeye-config [subcmd]         profiles + settings
    /bigeye --all                   dashboard without scope filter
   ```
   - Stable across runs. Never reorder.

8. Footer:
   ```
   Next: /bigeye-today     ({new_count} NEW issues waiting)
   More: /bigeye-rca {top_issue}  ·  /bigeye-table {top_table}  ·  /bigeye-incidents auto
   ```
   - Replace `Next:` with `Next: /bigeye-config init     (no profile configured yet)` when scope load failed.
   - When `state.last_table` is set, prefer it for the `More:` table reference; otherwise pick the highest-coverage in-scope table.

## State persistence

`/bigeye` is read-only. **Do not** write to `state.json` from this skill. Triage-style updates to `last_seen` for listed issues are **not** done here (the dashboard's job is to surface, not record). The next workflow skill the user runs (`/bigeye-today`) will refresh those.

## Errors

CLI / scope / parse errors per `preamble.md` Step 7.D. The dashboard never blocks rendering — partial sections are emitted with `(unavailable — <reason>)` placeholders inline.
````

- [ ] **Step 2: Verify**

```bash
grep -c "preamble.md\|output.md" skills/bigeye/SKILL.md
grep -c "## " skills/bigeye/SKILL.md
grep -c "Did you mean /bigeye-<x>" skills/bigeye/SKILL.md
grep -c "Routing\|intent" skills/bigeye/SKILL.md
```

Expected: at least 2 / 4+ / 1 / 0 (no more routing).

- [ ] **Step 3: Stage**

```bash
git add skills/bigeye/SKILL.md
```

---

## Task 14: Create `/bigeye-today` workflow skill

**Files:**
- Create: `skills/bigeye-today/SKILL.md`

**Context:** New skill. Reactive workflow: list open issues, pick one (or `a` for all-critical, or `c` for clusters), present action menu, delegate to atomic skill, return to action menu, exit on `[5] Back to issue list` or `[q]`. Multi-turn — keeps prompting until quit. Also has `--report-only` mode (used by the morning-report agent) which renders Turn 1 once and exits.

Delegation is verbatim — `/bigeye-today` doesn't duplicate triage / RCA / incidents / ticket logic. It only chains them.

- [ ] **Step 1: Create the directory and write the file**

Run:
```bash
mkdir -p skills/bigeye-today
```

Then write `skills/bigeye-today/SKILL.md` with exactly this content:

````markdown
---
name: bigeye-today
description: Use when the user wants to triage today's data quality issues — see what's open, pick one, act (RCA, close, group, ticket), and loop. Reactive workflow.
user-invocable: true
---

# BigEye Today

What it does: reactive workflow. Lists current open issues on the active scope, lets the user pick one (or auto-cycle through critical ones, or jump to clusters), then routes the picked issue through an action menu (RCA / close / group / ticket). Loops until the user quits. Composes existing atomic skills — does not duplicate their logic.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`.

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| (no arg) | Start the interactive loop | `/bigeye-today` |
| `--report-only` | Render Turn 1 only and stop (used by the scheduled morning agent) | `/bigeye-today --report-only` |

Global flags — see `output.md`.

## Procedure

### Turn 1 — list issues + picker

1. Follow `preamble.md` Steps 1–7. Read `settings.json.triage.max_issues`, `triage.default_brief_rows`, `view.default_view`.

2. Fetch open issues via CLI (same shape as `bigeye-triage`):
   ```bash
   TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
   trap 'rm -rf "$TMPDIR"' EXIT
   bigeye -w <profile> issues get-issues {-wid <id>} {-sn <name>} -op "$TMPDIR"
   ```
   Filter to `NEW + ACKNOWLEDGED + MONITORING`; apply scope; cap at `max_issues`.

3. Cluster count:
   - MCP on: per-issue `mcp__bigeye__list_related_issues`. Count groups.
   - MCP off: `cluster_count = null`.

4. Sort by `priorityScore` desc. Take top `default_brief_rows` (unless `default_view = "full"` or `--full`).

5. Join with `state.issues` to compute the `History` column.

6. Render Turn 1:
   ```
   {scope pill}
   ## Today — {open_count} open · {new_count} New · {ackd_count} Ack'd · {monitoring_count} Monitoring · {cluster_count} clusters

    # | Issue | Score | Dim       | Table    | Column | Since | History
    1 | 10921 |  87   | Freshness | orders   | —      | 2h    | rca (4d)
    ...
    (N more — add --full to see all)
   ```
   When `cluster_count = null`, replace with `cluster detection: unavailable`.

7. Update `state.json`: `last_workflow = "today"`. For every listed issue, update `last_seen` and `status_when_last_seen` (no `actions[]` write at this stage).

8. If `--report-only`: emit footer (same `Next: /bigeye-rca <top> ...` shape as triage) and stop.

9. Otherwise emit picker:
   ```
   Pick: [1-{N}], [a]ll critical, [c]lusters, <display_name>, /<slash_command>, [q]uit
   > _
   ```
   Wait for the user's response.

### Turn 2 — interpret picker input

User input rules:
- A digit `1`–`{N}` → load that row's issue (use the row's `displayName` and `id` from Turn 1's data). Render the action menu (Turn 3).
- A bare display name (e.g., `10925`) → fetch via CLI (`bigeye -w <profile> issues get-issues -iid` after MCP `search_issues` to map display → internal). Render the action menu.
- `a` → enumerate Critical-severity issues (per `output.md` rules) in order. For each, run Turn 3 RCA path (delegate to `/bigeye-rca <display>` via the Skill tool), and on return, move to the next. After the last, return to Turn 1.
- `c` → if `cluster_count == null`, print one-line note `Cluster detection unavailable — MCP not configured.` and return to picker.
   Otherwise, present the cluster list:
   ```
   ## Clusters

   ### Cluster 1: ({count} issues) — {auto_name}
    - #{display_1}, #{display_2}, ...
   ### Cluster 2: ...

   Pick a cluster number, or [b]ack:
   > _
   ```
   On a number → confirm `Create incident for {count} issues? (y/n)`. On `y`, delegate to `/bigeye-incidents <display_ids ...>` via the Skill tool. After the atomic skill returns, return to Turn 1.
- `/bigeye-<x> <args>` → exit the workflow entirely; hand off to the named atomic skill via the Skill tool. The workflow does not resume after the slash command returns.
- `q` → proceed to On-quit.
- Anything else → re-print the picker line.

### Turn 3 — action menu for a single issue

After loading the issue, render:
```
## Issue {display_name} — {dimension} on {schema}.{table_name}
Since: {time_since} · Priority: {priority_display} · Alerts: {alert_count}
History (local): {state.issues[<display>].actions joined as "skill (age)"}
Upstream: {top lineage hint from state.issues OR from a fresh MCP get_issue_lineage_trace if affordable, OR — if neither — "—"}

[1] Root-cause analysis           (/bigeye-rca)
[2] Close                          (true-positive / false-positive / expected)
[3] Group with related             (/bigeye-incidents auto, pre-filtered to this issue)
[4] Draft a ticket                 (/bigeye-ticket)
[5] Back to issue list
[q] Quit

> _
```

Action handling:
- `[1]` → invoke Skill tool with skill `bigeye-rca` and args `<display_name>`. On return, re-render the action menu.
- `[2]` → ask `Close as: [t]rue-positive / [f]alse-positive / [e]xpected / [b]ack? > _`. Map per `output.md`. Delegate to `/bigeye-incidents close <display> --label <mapped>`. On return, re-render menu.
- `[3]` → if MCP off, print one-line note and return to menu. Else delegate to `/bigeye-incidents <display> {related_displays}` (compute related_displays from a fresh `mcp__bigeye__list_related_issues` if not in cache). On return, re-render menu.
- `[4]` → invoke Skill tool with `bigeye-ticket` and args `<display_name>`. On return, re-render menu.
- `[5]` → return to Turn 1 (re-fetch is OK; or use Turn 1's cached list — implementer's choice).
- `[q]` → On-quit.
- Any slash command → exit workflow.

### On-quit

- Persist state: write final `last_*` pointers; run pruning per preamble Step 8.C.
- Emit a one-line summary:
  ```
  Session: {N} actions · {comma-separated "/skill #issue" or "/skill" for atomic invocations during this session}
  ```
- Footer:
  ```
  Next: /bigeye-today     (resume reactive triage)
  More: /bigeye  (dashboard)  ·  /bigeye-table  ·  /bigeye-config settings show
  ```

## Interaction rules

- Max menu depth = 1: Turn 1 (list) → Turn 3 (action menu). The cluster sub-prompt does not count as a depth — it returns to Turn 1.
- A slash command at any prompt exits the workflow.
- A bare display name is shorthand for "open that issue's action menu".
- State writes are batched: one final commit at quit, plus one atomic write per delegated atomic skill return (so crashes preserve progress).

## State persistence

On quit, follow `preamble.md` Step 8.B for the `bigeye-today` row:
- Set `state.json.last_workflow = "today"` (already set in Turn 1 step 7).
- Set `state.json.last_issue` to the most recent issue the user picked, if any.
- Atomic skills run from inside the workflow (RCA, incidents, ticket) write their own `actions[]` entries — do not duplicate.

Run pruning per Step 8.C.

## Errors

| Condition | Behavior |
|---|---|
| Empty issue list (after scope) | Print `No active issues in scope '{profile}' — all clear.` then footer + exit (no picker) |
| MCP off + `c` pick | one-line note `Cluster detection unavailable — MCP not configured.`; remain in picker |
| Invalid picker input | re-print picker; do not exit |
| Atomic skill error | propagate the atomic skill's `Error / Fix / Why` output verbatim; on return, re-render the prior menu (allowing retry) |
````

- [ ] **Step 2: Verify**

```bash
ls skills/bigeye-today/
wc -l skills/bigeye-today/SKILL.md
grep -c "Turn 1\|Turn 2\|Turn 3" skills/bigeye-today/SKILL.md
grep -c "preamble.md\|output.md" skills/bigeye-today/SKILL.md
```

Expected: file exists; ~150–200 lines; at least 6 turn references; at least 3 preamble/output references.

- [ ] **Step 3: Stage**

```bash
git add skills/bigeye-today/SKILL.md
```

---

## Task 15: Create `/bigeye-table` workflow skill

**Files:**
- Create: `skills/bigeye-table/SKILL.md`

**Context:** New skill. Proactive workflow: pick a table, render its status (coverage, open issues, monitor count, last action), present a menu (coverage / improve / deploy gaps / open issue / switch table / quit), delegate to the named atomic skill, return on completion. Multi-turn.

No-arg form: read `state.json.last_table`. Empty state → list top 5 recent in-scope tables from `state.tables`.

- [ ] **Step 1: Create the directory and write the file**

Run:
```bash
mkdir -p skills/bigeye-table
```

Then write `skills/bigeye-table/SKILL.md` with exactly this content:

````markdown
---
name: bigeye-table
description: Use when the user wants to audit a single table — coverage, weak monitors, gaps, or table-scoped issues. Proactive workflow.
user-invocable: true
---

# BigEye Table

What it does: proactive workflow. Pick a table; show its status card (coverage, open issues, monitor count, last local action); pick an action (coverage / improve / deploy gaps / open issue / switch table); delegate to the atomic skill; return to the card. Composes existing skills — does not duplicate their logic.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`.

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `<name>` | Start the loop for a named table (bare, `schema.table`, or `source.schema.table`) | `/bigeye-table orders` |
| (no arg) | Use `state.last_table`; if empty, list top 5 recent in-scope tables | `/bigeye-table` |

Global flags — see `output.md`.

## Procedure

### Turn 1 — table status card + picker

1. Follow `preamble.md` Steps 1–7.

2. Resolve the table name:
   - With arg, MCP on: `mcp__bigeye-knowledgebase__search_metadata` or `mcp__bigeye__list_tables` to resolve name → `table_id` + fully-qualified name. Ambiguous → numbered picker, wait.
   - With arg, MCP off: accept only fully-qualified `source.schema.table`. Bare name → hard-fail per Step 7.B with `feature_name=table-name resolution` and a Fix `/bigeye-table <source>.<schema>.<table>`. For the qualified form, resolve `table_id` via CLI:
     ```bash
     TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
     trap 'rm -rf "$TMPDIR"' EXIT
     bigeye -w <profile> catalog get-table-info -sn <schema> -tn <table> -op "$TMPDIR"
     ```
     and read the `id` field from the JSON.
   - No arg + `state.last_table` set: use it. Print `Table {fq} (last from prior session).`
   - No arg + `state.last_table` empty: list top 5 by `last_seen` from `state.tables` filtered by active scope, render as a picker. After user picks, continue.
   - No arg + state empty + active profile has resolved table_ids: pick the first one. Tell the user.
   - All else fails → ask `Which table?` and stop.

3. Fetch table state in one batch:
   - Coverage % via `mcp__bigeye__get_table_dimension_coverage` (skipped with `—` note if MCP off).
   - Open issues on the table:
     ```bash
     bigeye -w <profile> issues get-issues -tid <table_id> -op "$TMPDIR/issues"
     ```
     (or post-filter from a wider scope dump if `-tid` isn't supported by the version; fall back to grep `metricMetadata.datasetId`).
     Keep `NEW + ACKNOWLEDGED + MONITORING`.
   - Monitor count via:
     ```bash
     bigeye -w <profile> catalog get-metric-info -tid <table_id> -op "$TMPDIR/metrics"
     ```
   - Local history from `state.tables[<fq>]`.

4. Render the table card:
   ```
   {scope pill}
   ## Table — {schema}.{table_name}
   Coverage: {coverage_pct or "—"} · {monitor_count} monitors · {open_issue_count} open issues · last deploy: {last_deploy_note or "—"} ({age or "—"})

   Open issues on this table:
    # | Issue | Dim       | Column | Since
    1 | 10921 | Freshness | —      | 2h
    ...
   {(N more — add --full to see all) when truncated}

   [1] Coverage report               (/bigeye-coverage)
   [2] Improve monitors              (/bigeye-improve)
   [3] Deploy gaps                   (/bigeye-deploy gaps)
   [4] Open issue                    (1, 2, or 3 above)
   [5] Switch table
   [q] Quit

   Pick: [1-5], [q]uit
   > _
   ```

### Turn 2 — interpret menu input

- `[1]` → delegate via Skill tool to `bigeye-coverage` with arg `<fq>`. On return, re-render Turn 1.
- `[2]` → delegate to `bigeye-improve` with arg `<fq>`. On return, re-render Turn 1.
- `[3]` → delegate to `bigeye-deploy` with args `gaps` (scope-flags pass through internally — the active profile's table-restricted scope makes "gaps" apply only to this table; if the profile is broader, scope down to this table for the duration of the delegation). On return, re-render Turn 1.
- `[4]` → if no open issues, one-line note `No open issues on this table.`; remain in menu. Else: ask `Issue number? > _` then hand the chosen issue to `/bigeye-today` Turn 3 action menu (delegate via Skill tool; bigeye-today's existing arg-handling for a single display name will pick this up).
- `[5]` → ask `Table name? > _`. Restart Turn 1 with the new name.
- `[q]` → On-quit.
- Any slash command → exit the workflow.
- Anything else → re-print Turn 1 footer line.

### On-quit

- Persist state: `last_workflow = "table"`; `last_table = "<fq>"`; pruning per Step 8.C.
- Emit a one-line summary:
  ```
  Session: {N} actions · {comma-separated "/skill" tags}
  ```
- Footer:
  ```
  Next: /bigeye-today     (back to reactive triage)
  More: /bigeye  (dashboard)  ·  /bigeye-table  ·  /bigeye-config settings show
  ```

## Interaction rules

- Max menu depth = 1: Turn 1 (card) → Turn 3 (delegated atomic skill output) → return to Turn 1.
- A slash command at any prompt exits the workflow.
- State writes are batched: one final commit at quit, plus one atomic write per delegated atomic skill return.

## State persistence

On quit, follow `preamble.md` Step 8.B for the `bigeye-table` row:
- Set `state.json.last_workflow = "table"`.
- Set `state.json.last_table = "<fq>"`.
- Atomic skills run from inside the workflow (coverage, improve, deploy) write their own `actions[]` entries — do not duplicate.

Run pruning per Step 8.C.

## Errors

| Condition | Behavior |
|---|---|
| Bare-name resolution fails (MCP off) | hard-fail per Step 7.B with workaround `Re-run with <source>.<schema>.<table>` |
| Bare-name resolution ambiguous (MCP on) | numbered picker; wait for choice |
| Table not found | print CLI / MCP error per Step 7.D; offer `Switch table` |
| Atomic skill error | propagate `Error / Fix / Why` block; on return, re-render Turn 1 |
````

- [ ] **Step 2: Verify**

```bash
ls skills/bigeye-table/
wc -l skills/bigeye-table/SKILL.md
grep -c "preamble.md\|output.md" skills/bigeye-table/SKILL.md
grep -c "state.last_table\|state.tables" skills/bigeye-table/SKILL.md
```

Expected: file exists; ~120–180 lines; at least 3 preamble/output refs; at least 2 state refs.

- [ ] **Step 3: Stage**

```bash
git add skills/bigeye-table/SKILL.md
```

---

## Task 16: Retarget `bigeye-morning-report` agent

**Files:**
- Modify (rewrite): `agents/bigeye-morning-report.md`

**Context:** Today's agent inlines triage + cluster + coverage. After redesign, it calls `/bigeye-today --report-only` for the issue+cluster section, keeps its own coverage scoring, and reads Slack settings from `settings.json.slack`.

- [ ] **Step 1: Overwrite the file**

Replace the entire contents of `agents/bigeye-morning-report.md` with:

````markdown
---
name: bigeye-morning-report
description: |
  Scheduled daily agent that produces a BigEye data quality summary and sends a Slack notification. Use with: /schedule create "0 8 * * *" /bigeye-morning-report
model: inherit
---

You are the BigEye Morning Report agent. Your job is to produce a daily data quality summary for the team and send a short notification to Slack.

**IMPORTANT: You are read-only. You NEVER modify issues, create monitors, or take any write actions. You only observe and report.**

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection. Output shape lives in `skills/bigeye/references/output.md`. Slack channel + mention group come from `~/.claude/bigeye-plugin/settings.json` (`slack.channel`, `slack.mention_group`, `slack.critical_only`).

## Workflow

### 0. Load scope

Follow `preamble.md` Steps 1–7. If no profile is configured, stop and print:
```
Cannot run morning report — no BigEye profile configured. Run `/bigeye-config init` once on this machine.
```

(The agent cannot run the interactive wizard because there is no user present.)

### 1. Triage — call `/bigeye-today --report-only`

Invoke the `bigeye-today` skill (via the Skill tool) with arg `--report-only`. This runs Turn 1 of the today workflow non-interactively and returns the rendered scope pill, the issue table, and the per-status summary line. Capture its output verbatim — it is the body of Section 1.

This replaces the agent's prior inline issue-fetch + filter + classify steps. The agent does not duplicate that logic.

### 2. Coverage check (kept as-is from prior design)

If `MCP_AVAILABLE = false`:
  Skip coverage scoring. Set `coverage_percent = "skipped (MCP unavailable)"`. Do not call MCP.

If `MCP_AVAILABLE = true`:
  For each in-scope table (from preamble Step 1.E's `table_ids` / resolved `table_names`), call `mcp__bigeye__get_table_dimension_coverage`. Record the overall coverage percentage. If multiple tables are in scope, report the average or list them individually (whichever fits within the Slack template).

  If the working profile has no tables (empty profile or `--no-scope`), skip and report coverage as `n/a (no tables in scope)`.

### 3. Produce terminal report

```
{scope pill}
## Morning Report — {date} {time}

### Current State
{output captured from /bigeye-today --report-only}

### Coverage
{coverage_pct or "skipped (MCP unavailable)"}%

### Action Items
1. {If clusters: "Group related issues: /bigeye-incidents auto"}
2. {If critical: "Investigate top critical: /bigeye-rca {top_issue}"}
3. {If unacknowledged > 5: "Triage unacknowledged: /bigeye-today"}
4. {If coverage < 80%: "Review monitoring gaps: /bigeye-coverage"}
```

### 4. Send Slack notification

Read Slack config from `settings.json.slack`:
- `channel` — the Slack channel to post to
- `mention_group` — the group to ping
- `critical_only` — when true, send only when there are NEW Critical issues; when false, send daily

If sending: authenticate with Slack MCP if needed (`mcp__claude_ai_Slack__authenticate` / `complete_authentication`), then send a message:

```
BigEye Morning Report — {date}

{critical_count} critical | {warning_count} warning | {low_count} low

Top issues:
- #{issue_1}: {dimension} on {column} ({time_since})
- #{issue_2}: {dimension} on {column} ({time_since})
- #{issue_3}: {dimension} on {column} ({time_since})

Coverage: {percent}%
Run /bigeye-today in Claude Code for details
```

If `critical_count > 0`, prepend with the `slack.mention_group` value.

If `slack.critical_only == true` and `critical_count == 0`, skip the Slack send entirely — don't create noise on quiet days.

If MCP was unavailable, the Slack template's Coverage line reads `Coverage: n/a (MCP unavailable)`.

## State persistence

The agent does not write to `state.json` directly. The skill it composes (`bigeye-today --report-only` in Step 1) handles its own state writes via preamble Step 8.B.
````

- [ ] **Step 2: Verify**

```bash
grep -c "preamble.md\|output.md" agents/bigeye-morning-report.md
grep -c "settings.json.slack" agents/bigeye-morning-report.md
grep -c "/bigeye-today --report-only" agents/bigeye-morning-report.md
grep -c "conventions.md\|scope.md\|cli.md" agents/bigeye-morning-report.md
```

Expected: at least 2 / 1 / 1 / 0.

- [ ] **Step 3: Stage**

```bash
git add agents/bigeye-morning-report.md
```

---

## Task 17: Bump version, update README, delete old reference files

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `README.md`
- Delete: `skills/bigeye/references/scope.md`
- Delete: `skills/bigeye/references/cli.md`
- Delete: `skills/bigeye/references/conventions.md`

**Context:** Final release polish. Bump both manifest versions to `0.4.0`. Rewrite the README to lead with the workflow commands + dashboard. Remove the stub reference files (the upgrade has stabilized — anything that linked to them now follows the in-stub pointers to `preamble.md`/`output.md`).

The upgrade-notice logic is already wired into `preamble.md` Step 8.E (Task 1). It triggers on first skill invocation after upgrade and flips `_meta.upgrade_seen = true` after printing.

- [ ] **Step 1: Bump `plugin.json` version**

Edit `.claude-plugin/plugin.json` — change `"version": "0.3.0"` to `"version": "0.4.0"`.

- [ ] **Step 2: Bump `marketplace.json` version**

Edit `.claude-plugin/marketplace.json` — change the `"version": "0.3.0"` inside `plugins[0]` to `"version": "0.4.0"`.

- [ ] **Step 3: Verify both versions**

```bash
grep '"version"' .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

Expected: both show `"version": "0.4.0"`.

- [ ] **Step 4: Rewrite README.md**

Replace the entire contents of `README.md` with:

````markdown
# BigEye Data Observability Plugin

A Claude Code plugin for managing BigEye monitoring at scale — built around two workflows (reactive triage and proactive table audits), backed by a persistent dashboard, and chained through atomic skills with consistent output and a local activity log.

## What's new in 0.4.0

- **Two workflow commands** — `/bigeye-today` (reactive: triage → act → loop) and `/bigeye-table <name>` (proactive: audit a table → act → loop). These compose the existing atomic skills; you don't have to remember which command to chain next.
- **`/bigeye` is now a dashboard.** One-pass snapshot of your scope: open issues, recent activity, per-table coverage, last actions. Non-interactive.
- **Settings file.** User-editable values (Slack channel, severity thresholds, deploy defaults, default view) moved out of plugin files into `~/.claude/bigeye-plugin/settings.json`. Manage via `/bigeye-config settings show` / `settings edit <key> <value>`.
- **Activity log.** A new `~/.claude/bigeye-plugin/state.json` records every skill action per issue and per table. No-arg forms (`/bigeye-rca`, `/bigeye-coverage`, `/bigeye-improve`, `/bigeye-table`) resume from where you left off.
- **Standardized output.** Scope pill, Brief/Full sizing, `Next:`/`More:` footer, `Error / Fix / Why` blocks across every skill.
- **Backwards-compatible on disk.** No command renames or removals. `profiles.json` and ticket templates are preserved on upgrade.

If you customized the old `conventions.md` reference (Slack channel or severity thresholds) in a previous version, those edits are not migrated automatically — re-apply them via `/bigeye-config settings edit slack.channel '#your-channel'`, etc.

## Requirements

- Claude Code with plugin support
- **Bigeye CLI 0.7+** installed and authenticated — see [`bigeye-cli-install.md`](bigeye-cli-install.md)
- **Bigeye MCP server** (optional; unlocks RCA lineage, coverage scoring, incident creation, cluster detection, display-name lookup, and tag tracking) — see [`bigeye-mcp-install.md`](bigeye-mcp-install.md)
- Slack MCP server (optional, for morning report notifications)

## Installation

```bash
/plugin marketplace add andriikoziichuk/bigeye-plugin
/plugin install bigeye-plugin@andriikoziichuk-bigeye-plugin
```

After install: `/bigeye-config init` once to bind your workspace and scope filters.

## Workflows (start here)

| Command | When to use |
|---|---|
| `/bigeye` | Quick snapshot — what's the state of my scope right now? |
| `/bigeye-today` | Something's broken — show me open issues, let me act. |
| `/bigeye-table <name>` | Audit a table — coverage, weak monitors, gaps, table-scoped issues. |

## Atomic skills (called by workflows; usable directly too)

| Command | Description |
|---|---|
| `/bigeye-config [init/show/switch/add/edit/delete/verify/settings show/settings edit]` | Manage scope profiles (`profiles.json`) and user settings (`settings.json`). |
| `/bigeye-triage [new/24h/<N>]` | Prioritized active issues, scope-filtered. |
| `/bigeye-rca [issue]` | Root-cause analysis with lineage tracing. No-arg → resumes `last_issue`. |
| `/bigeye-coverage [table]` | Dimension/column gaps + cheap weak-monitor scan. No-arg → resumes `last_table`. |
| `/bigeye-improve [table]` | Deep monitor recommendations + heavy-mode SQL refinement loop. No-arg → resumes `last_table`. |
| `/bigeye-deploy [target]` | Create monitors with confirmation gate. |
| `/bigeye-incidents [ids/auto/add/close]` | Group related issues into incidents. |
| `/bigeye-ticket [issue]` | Render a markdown vendor ticket from a user-authored template. |

## Scheduled agent

Set up the daily morning report:
```bash
/schedule create "0 8 * * *" /bigeye-morning-report
```
The agent calls `/bigeye-today --report-only` under the hood and posts to Slack (`settings.json.slack.channel`).

## Configuration

**Scope profiles** (`~/.claude/bigeye-plugin/profiles.json`) — owned by `/bigeye-config`. Workspace + filter sets (data sources, tables, schemas). Per-invocation overrides: `--profile <name>`, `--no-scope`, `--workspace <id>`.

**Settings** (`~/.claude/bigeye-plugin/settings.json`) — Slack channel, severity thresholds, deploy defaults, default view. Seeded on first run. Edit via `/bigeye-config settings show` / `settings edit <key> <value>`.

**Activity log** (`~/.claude/bigeye-plugin/state.json`) — append-only, LRU-pruned (last 500 issues, last 100 tables). Backs no-arg fallbacks and the dashboard's "History" / "Recently closed" sections.

**Ticket templates** (`~/.claude/bigeye-plugin/ticket-templates/`) — managed via `/bigeye-ticket templates add/edit/delete/list`. Seeded with a `default.md` on first run.

## How features degrade without MCP

The Bigeye CLI is the primary transport. MCP unlocks lineage, clustering, coverage scoring, incidents, display-name lookup, profile data, and tag tracking. When MCP is unavailable, every skill prints a one-line note and continues with whatever the CLI alone can show. Some operations hard-fail (coverage scoring, incident creation, display-name lookup) — those skills print a clear pointer to `bigeye-mcp-install.md`.

Run `/bigeye-config verify` to see exactly what's enabled.
````

- [ ] **Step 5: Delete the old reference stubs**

```bash
git rm skills/bigeye/references/scope.md skills/bigeye/references/cli.md skills/bigeye/references/conventions.md
```

(`git rm` stages the deletion in one step. The user owns the commit.)

- [ ] **Step 6: Verify the deletions and the README**

```bash
ls skills/bigeye/references/
grep -c "/bigeye-today\|/bigeye-table" README.md
grep -c "What's new in 0.4.0" README.md
```

Expected: only `improve.md`, `preamble.md`, `output.md` remain in `references/`. README mentions `/bigeye-today` / `/bigeye-table` at least 3 times. README has the "What's new" section.

- [ ] **Step 7: Stage the manifest + README changes**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json README.md
```

(The deletions from Step 5 are already staged.)

---

## Task 18: Manual verification scenarios

**Files:** none modified in this task.

**Context:** Skills are markdown — no automated test suite. After all prior tasks complete, run these scenarios end-to-end on a real workspace. Each one maps to a section of the spec's §Verification.

A failed scenario should produce a fix-up commit before merge; the user owns the merge decision.

- [ ] **Scenario 18.1: preamble + output refs + settings**

1. With a fresh `~/.claude/bigeye-plugin/` (or after deleting `settings.json`), run `/bigeye-triage`. Expect: one line `Wrote ~/.claude/bigeye-plugin/settings.json with defaults — edit via /bigeye-config settings.` followed by normal triage output.
2. Run `/bigeye-config settings show`. Expect: the seeded JSON, pretty-printed.
3. Run `/bigeye-config settings edit slack.channel '#test-data'`. Expect: `Updated slack.channel: #data-quality-alerts -> #test-data`.
4. Run `/bigeye-config settings show` again. Expect: `slack.channel == "#test-data"`.
5. Run `/bigeye-config settings edit slack.channel '#data-quality-alerts'` to restore.

- [ ] **Scenario 18.2: atomic skills with MCP on (live workspace)**

For each of `bigeye-triage`, `bigeye-rca <known-issue>`, `bigeye-coverage <known-table>`, `bigeye-improve <known-table> --light`, `bigeye-incidents auto`, `bigeye-ticket <known-issue>`:
1. Run the command.
2. Expect:
   - Line 1 is the scope pill in the new format (`[profile · workspace · facets]`).
   - Brief shape (top 10 rows + truncation marker if more exist).
   - Footer with `Next:` / `More:` lines.
   - No references to `conventions.md` / `scope.md` / `cli.md` in the output.
3. Use `Read` on `~/.claude/bigeye-plugin/state.json` to confirm the expected entries appeared (per the per-skill state-write table in `preamble.md` Step 8.B).

- [ ] **Scenario 18.3: atomic skills with MCP off**

Disable Bigeye MCP (or run on a host where it's not configured). Repeat scenario 18.2:
1. `bigeye-triage` — cluster section replaced with a one-line note; rest renders.
2. `bigeye-rca 10921` — hard-fails with `Error / Fix / Why` block pointing at `--internal-id`.
3. `bigeye-rca 42 --internal-id` — works; lineage/related/resolution sections show `(skipped — MCP unavailable)`.
4. `bigeye-coverage <table>` — hard-fails per Step 7.B.
5. `bigeye-improve <table> --light` — Weak Monitors section populated; no Coverage Suggestions.
6. `bigeye-incidents auto` — hard-fails per Step 7.B.
7. `bigeye-ticket --internal-id 42` — renders, with MCP-only `{{vars}}` substituted with `_(unavailable — MCP not configured)_` and a footer note.

- [ ] **Scenario 18.4: state.json no-arg fallbacks**

1. Run `/bigeye-rca 10921` (with MCP on). Use `Read` on `state.json`: `last_issue == "10921"` and `issues["10921"].actions[-1].skill == "bigeye-rca"`.
2. Run `/bigeye-rca` (no arg). Expect one line `Resuming issue 10921 from previous session.` followed by a normal RCA output.
3. Run `/bigeye-coverage <known-table>`. Use `Read`: `last_table` is set; `tables[<fq>].actions[-1].skill == "bigeye-coverage"`.
4. Run `/bigeye-coverage` (no arg). Expect `Coverage on <fq> (last table from prior session).`.
5. Run `/bigeye-improve` (no arg). Expect `Improving <fq> (last table from prior session).`.

- [ ] **Scenario 18.5: state.json pruning**

1. With a Python or `jq` snippet, write 600 fake issue entries into `state.json`. Save.
2. Run any skill that writes state (e.g., `/bigeye-rca <known-issue>` with MCP on).
3. Use `Read` on `state.json`: `len(issues) <= 500`. The fake entries with the oldest `last_seen` should be gone; the real new entry should be present.

- [ ] **Scenario 18.6: dashboard**

1. Run `/bigeye`. Expect: scope pill; `## BigEye Dashboard — <weekday> ...`; `Status:` line with counts; `Last:` line referencing real activity from state.json (or the empty fallback line); top-5 issue table with `History` column populated; possibly `Recently closed` section; `Your tables` section with coverage + open + last-action; `Commands:` cheatsheet; `Next:` / `More:` footer.
2. Run `/bigeye --all`. Expect: scope pill shows `NO-SCOPE` or removes facets; the issue + tables sections widen.
3. Run `/bigeye frobnicate`. Expect: a `Did you mean /bigeye-<x> frobnicate? /bigeye shows the dashboard; individual commands run tasks.` line above the dashboard.

- [ ] **Scenario 18.7: `/bigeye-today` end-to-end**

1. Run `/bigeye-today`. Expect Turn 1 output (scope pill, `## Today — N open · …`, issue table, picker).
2. Type `1`. Expect Turn 3 action menu for issue at row 1.
3. Type `1` again. Expect `/bigeye-rca <display>` to run; on return, the action menu re-renders.
4. Type `5`. Expect Turn 1 to re-render.
5. Type `q`. Expect a one-line `Session: N actions · …` summary then footer.
6. Run `/bigeye-today --report-only`. Expect Turn 1 output then footer. No picker prompt.
7. Run `/bigeye-today`, then at the picker type `/bigeye-rca 10925`. Expect the workflow to exit and `bigeye-rca` to run.

- [ ] **Scenario 18.8: `/bigeye-table` end-to-end**

1. Run `/bigeye-table <known-table>`. Expect Turn 1 (status card + menu).
2. Type `1`. Expect coverage to run; on return, the card re-renders.
3. Type `5`, then a different table name. Expect Turn 1 for the new table.
4. Type `q`. Expect summary + footer; `state.last_table` updated.
5. Run `/bigeye-table` (no arg). Expect: Turn 1 for the last table from the prior step.
6. Delete `state.json` (or zero `last_table`). Run `/bigeye-table` (no arg). Expect: top-5 in-scope tables picker.
7. With MCP off, run `/bigeye-table <bare-name>`. Expect: hard-fail with `Re-run with <source>.<schema>.<table>`.

- [ ] **Scenario 18.9: morning agent**

1. Run `/bigeye-morning-report` (or simulate the scheduled run). Expect: terminal report with `Current State` from `/bigeye-today --report-only`, coverage section, action items.
2. Edit `settings.json.slack.channel` to a safe test channel; run again with at least one Critical issue. Expect: Slack post lands in the test channel; mention group present; coverage line reads the value or the `n/a (MCP unavailable)` placeholder.

- [ ] **Scenario 18.10: upgrade notice**

1. Edit `settings.json._meta.upgrade_seen` to `false`.
2. Run any skill (e.g., `/bigeye-triage`). Expect: the upgrade notice line `Upgraded to bigeye-plugin 0.4.0. New: ...` immediately after preamble setup, before the skill's normal output.
3. Run the same skill again. Expect: no upgrade notice (flag is now `true`).
4. Try `/bigeye-config settings edit _meta.upgrade_seen false`. Expect: `Error: _meta.upgrade_seen is managed by the plugin.`

- [ ] **Scenario 18.11: version + manifests + reference cleanup**

1. `Read` `.claude-plugin/plugin.json` → `"version": "0.4.0"`.
2. `Read` `.claude-plugin/marketplace.json` → `plugins[0].version == "0.4.0"`.
3. `ls skills/bigeye/references/` — only `improve.md`, `preamble.md`, `output.md`.
4. `grep` README.md for `What's new in 0.4.0`, `/bigeye-today`, `/bigeye-table`. All must match.

Report any failures; the user owns decisions on whether each blocks merge.

---

## Self-Review Notes (for the implementer)

- **Tasks 1–4** are foundational. All later atomic-skill rewrites depend on `preamble.md` and `output.md` existing. Don't re-order — keep them first.
- **Tasks 6–12** (atomic skill rewrites) can be parallelized after 1–4 are complete: each skill is independent. Subagent-driven workers can fan out.
- **Tasks 13–15** (dashboard, today, table) depend on 1–12. Skip ahead at your peril — they reference state-write semantics defined in Task 1's preamble.
- **Task 16** (agent retarget) depends on Task 14 (`/bigeye-today --report-only` must exist).
- **Task 17** is final-only. It deletes the stubs from Task 4. Don't merge Task 17 ahead of any later task that still references the stubs.
- **Task 18** is a checklist, not code. Run it on a real workspace.
- The user's preferences (from memory): never run `git commit` (every task ends with `git add` only); never run `git init`; edit files in `~/PycharmProjects/bigeye-plugin/` (not the plugin cache).
- This plan does not introduce any new external services, web endpoints, or third-party dependencies. All changes are markdown + JSON manifests.