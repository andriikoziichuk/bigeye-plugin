# BigEye Plugin — UX Redesign (v0.4.0)

**Status:** Draft · Date: 2026-04-24 · Target version: `0.4.0`

## Purpose

The plugin today exposes 9 skills that each solve one slice of a data-quality workflow. End users (the primary audience for this redesign) have to chain these skills manually, remember different argument syntaxes, and parse dense outputs. This spec redesigns the command surface around the two dominant workflows real users run — reactive triage and proactive table audits — while tightening the skill and output layer underneath.

Scope: **full redesign, backwards-compatible on disk.** No renames, no command removals, no schema changes to `profiles.json` or ticket templates. New files and behaviors are additive. A single version bump (0.3.0 → 0.4.0) ships the whole change.

## Goals

1. Collapse the "which command do I run?" decision into two primary commands that mirror how users actually work.
2. Give users a persistent dashboard (`/bigeye`) that shows current issues on their tables, with local history of what they've acted on.
3. Remove duplication across SKILL.md files by consolidating the scope/CLI/MCP preamble into one reference doc.
4. Move user-editable configuration (Slack channel, severity thresholds, deploy defaults) out of plugin files and into a user-owned `settings.json`.
5. Standardize output shape across every skill: scope pill, Brief/Full sizing, `Next:` / `More:` footer, `Error / Fix / Why` format.

## Non-goals

- No changes to the scope-profile schema or to `~/.bigeye/` files.
- No intelligence-layer changes — `improve.md` stays as-is.
- No browser/web UI work (user declined). Terminal-only.
- No renames or command removals. Muscle memory is preserved.

---

## Architecture

### Command surface

| Command | Status | Role |
|---|---|---|
| `/bigeye` | Rewritten as **dashboard** | One-screen view: current issues on the active scope, local activity log, cheatsheet. Non-interactive. |
| `/bigeye-today` | **NEW (primary)** | Reactive workflow: open issues → pick one → act (RCA / close / group / ticket) → loop. Stateful multi-turn. |
| `/bigeye-table <name>` | **NEW (primary)** | Proactive workflow: pick a table → show status → act (coverage / improve / deploy / issues) → loop. Stateful multi-turn. |
| `/bigeye-config` | Kept, extended | Profiles + `settings.json` + `verify`. Adds `settings show|edit <key>`. |
| `/bigeye-triage` | Kept, tightened | Atomic. Building block called by `/bigeye-today`. |
| `/bigeye-rca [issue]` | Kept, tightened | Atomic. No-arg form resolves from `state.json.last_issue`. |
| `/bigeye-coverage [table]` | Kept, tightened | Atomic. No-arg form resolves from `state.json.last_table`. |
| `/bigeye-improve [table]` | Kept, tightened | Atomic. No-arg form resolves from `state.json.last_table`. |
| `/bigeye-deploy [target]` | Kept, tightened | Atomic. Mandatory confirmation gate unchanged. |
| `/bigeye-incidents [ids\|auto]` | Kept, tightened | Atomic. |
| `/bigeye-ticket [issue]` | Kept, tightened | Atomic. |
| `bigeye-morning-report` (agent) | Retargeted | Calls `/bigeye-today --report-only` under the hood; no menu. |

### Directory layout (after redesign)

```
bigeye-plugin/
  .claude-plugin/
    plugin.json                           # version 0.4.0
    marketplace.json
  agents/
    bigeye-morning-report.md              # retargeted to /bigeye-today --report-only
  hooks/
    hooks.json                            # unchanged
  skills/
    bigeye/
      SKILL.md                            # rewritten as dashboard
      references/
        preamble.md                       # NEW — merged scope.md + cli.md
        output.md                         # trimmed conventions.md (formatting only)
        improve.md                        # unchanged
    bigeye-today/
      SKILL.md                            # NEW — reactive workflow
    bigeye-table/
      SKILL.md                            # NEW — proactive workflow
    bigeye-config/
      SKILL.md                            # extended with settings sub-commands
    bigeye-triage/SKILL.md                # tightened
    bigeye-rca/SKILL.md                   # tightened, no-arg uses state
    bigeye-coverage/SKILL.md              # tightened, no-arg uses state
    bigeye-improve/SKILL.md               # tightened, no-arg uses state
    bigeye-deploy/SKILL.md                # tightened
    bigeye-incidents/SKILL.md             # tightened
    bigeye-ticket/
      SKILL.md                            # tightened
      templates/default.md                # unchanged
  bigeye-cli-install.md                   # unchanged
  bigeye-mcp-install.md                   # unchanged
  README.md                               # rewritten, leads with workflows + dashboard
```

### User-owned files

| Path | Status | Purpose |
|---|---|---|
| `~/.claude/bigeye-plugin/profiles.json` | Unchanged schema | Scope profiles (workspace + data_source_ids + table_ids + table_names + schema_names). **Source of truth** for "who is responsible for what". |
| `~/.claude/bigeye-plugin/ticket-templates/*.md` | Unchanged | Ticket template bodies. |
| `~/.claude/bigeye-plugin/settings.json` | **NEW** | User-editable config previously hardcoded in `conventions.md`. Seeded on first run. |
| `~/.claude/bigeye-plugin/state.json` | **NEW** | Append-only activity log: per-issue and per-table action history; `last_issue`, `last_table`, `last_workflow`. No TTL. LRU-pruned (last 500 issues, last 100 tables). |
| `~/.bigeye/config.ini` | Unchanged | CLI workspace binding. |
| `~/.bigeye/credentials` | Unchanged | User-owned CLI auth. |

### Settings file schema

`~/.claude/bigeye-plugin/settings.json`:

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

Rules:
- Read at the start of every skill run (after preamble). Missing file → seed with defaults silently on first encounter; write. Missing top-level key → use the shipped default for that key (forward-compatible).
- Managed only via `/bigeye-config settings show|edit <key>`. Never edited by any other skill.
- `default_view` accepts `brief` or `full`. Power users who want Full by default set it here; per-invocation `--full`/`--limit` always wins.

### State file schema

`~/.claude/bigeye-plugin/state.json`:

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
        { "skill": "bigeye-rca", "at": "2026-04-20T09:14:00Z" },
        { "skill": "bigeye-incidents", "at": "2026-04-21T10:30:00Z", "note": "grouped with 10922, 10923" },
        { "skill": "bigeye-ticket", "at": "2026-04-22T11:05:00Z" }
      ]
    }
  },
  "tables": {
    "warehouse.public.orders": {
      "first_seen": "2026-04-18T08:00:00Z",
      "last_seen": "2026-04-24T09:15:00Z",
      "actions": [
        { "skill": "bigeye-coverage", "at": "2026-04-18T08:02:00Z" },
        { "skill": "bigeye-improve", "at": "2026-04-18T08:40:00Z" },
        { "skill": "bigeye-deploy", "at": "2026-04-18T09:05:00Z", "note": "3 monitors created" }
      ]
    }
  }
}
```

Rules:
- Append-only. Every atomic skill, on successful completion, appends one entry to `actions[]` of the relevant issue and/or table, and updates `last_*` pointers.
- Writes are atomic: write `state.json.tmp` in the same directory, then rename.
- No TTL. Closed issues remain in the log.
- Pruning: when `issues` exceeds 500 keys or `tables` exceeds 100 keys, drop entries by oldest `last_seen` until under the cap. Pruning runs at the end of any skill that wrote.
- Readable to no-arg commands: `/bigeye-rca` without an issue uses `last_issue`; `/bigeye-coverage` and `/bigeye-improve` without a table use `last_table`; empty state → ask the user.

---

## Shared preamble (replaces today's 3-file preamble in every skill)

Every SKILL.md opens with exactly one line:

> `Follow skills/bigeye/references/preamble.md for scope, CLI, and MCP detection before any BigEye call.`

`preamble.md` consolidates today's `scope.md` + `cli.md` into a single ordered procedure. Sections:

1. **Step 1 — Load scope profile** (today's scope.md Steps A–E: locate file, select profile, apply overrides, resolve table names, build parameter map).
2. **Step 2 — Bind CLI workspace** (today's cli.md Step A).
3. **Step 3 — Detect MCP** (today's cli.md Step B — call `mcp__bigeye__list_data_sources`; set `MCP_AVAILABLE`; do not retry).
4. **Step 4 — Apply per-skill scope rules** (today's scope.md Step F — the per-skill matrix moves here, single source).
5. **Step 5 — Emit scope pill** (new format; see Output section).
6. **Step 6 — MCP-absent warning template** (today's cli.md Step F; unchanged text).
7. **Step 7 — Error handling rules** (today's cli.md Step G; text reformatted to the new `Error / Fix / Why` shape).
8. **Step 8 — Persist to state.json** (new — every skill, on successful return, appends to `actions[]` and updates `last_*`; pruning runs here).

Output doc (`output.md`) becomes the **only** place formatting lives: display mappings, severity class labels, scope pill format, Brief/Full rules, footer format, error format. No Slack or threshold config — those move to `settings.json`.

---

## Workflow specifications

### `/bigeye-today`

**Argument grammar:**

| Invocation | Purpose |
|---|---|
| `/bigeye-today` | Start interactive loop |
| `/bigeye-today --report-only` | Non-interactive — render Turn 1 output and stop (used by the scheduled morning agent) |
| `/bigeye-today --profile <n>` / `--no-scope` / `--workspace <id>` | Standard global flags |

**Procedure:**

**Turn 1 — list issues + picker:**

1. Follow `preamble.md`.
2. Read `settings.json` → `triage.max_issues`, `triage.default_brief_rows`, `view.default_view`.
3. Fetch open issues via CLI: `bigeye -w <profile> issues get-issues -wid <...> -sn <...> -op "$TMPDIR"`.
4. Filter to `ISSUE_STATUS_NEW + ACKNOWLEDGED + MONITORING`; apply scope; cap at `max_issues`.
5. If `MCP_AVAILABLE=true`: call `mcp__bigeye__list_related_issues` per issue to compute cluster count. Else: `cluster_count = null`.
6. Sort by `priorityScore` desc. Take top `default_brief_rows` (unless `default_view=full` or `--full` given).
7. Join with `state.json.issues` to compute per-issue "History" column (short skill tags + age: `rca (4d), inc (3d)`).
8. Render as per the mockup in section "Output samples" below.
9. Append-to-state: update `last_seen` and `status_when_last_seen` for every listed issue; set `last_workflow="today"`.
10. If `--report-only`: stop here.
11. Otherwise emit the picker prompt:

    ```
    Pick: [1-N], [a]ll critical, [c]lusters, <display_name>, /<slash_command>, [q]uit
    > _
    ```

**Turn 2 — action menu for a single issue:**

User typed `1`, `10921`, or `a`:

- `a` → iterate through the Critical-severity issues (per `output.md` severity rules) in order, running Turn 3 RCA for each, returning to Turn 1 at the end.
- `c` → present cluster groups; user picks one; issue numbers collapse into a "create incident?" confirmation (delegates to `/bigeye-incidents <ids>` with pre-filled IDs).
- A number or display name → load that issue (CLI `issues get-issues -iid <id> -op ...`), render the issue card:

  ```
  ## Issue 10921 — Freshness on warehouse.public.orders
  Since: 2h ago · Priority: High · Alerts: 3
  History (local): rca (4d ago), incident (3d ago)
  Upstream: <top lineage hint from state or MCP>

  [1] Root-cause analysis           (/bigeye-rca)
  [2] Close                          (true-positive / false-positive / expected)
  [3] Group with related             (/bigeye-incidents auto — pre-filtered to this issue's cluster)
  [4] Draft a ticket                 (/bigeye-ticket)
  [5] Back to issue list
  [q] Quit
  > _
  ```

- `/bigeye-rca 10925` (typed directly) → escape hatch: exit the workflow and hand off to the atomic skill with the given arg.

**Turn 3+ — delegation:**

On action pick, delegate to the atomic skill with the internal issue ID in-scope. When the atomic skill returns, re-show the action menu for the same issue. User exits back to the issue list via `[5]`, quits via `[q]`.

**On quit:**

- Persist state (prune if needed).
- Emit a one-line summary: `Session: 3 actions · /bigeye-rca #10921 · /bigeye-ticket #10921 · /bigeye-incidents auto`.
- Standard `Next:` / `More:` footer.

**Interaction rules:**

- Max 1 menu depth (list → action menu → delegate → back). No nested menus.
- At any prompt, a slash command (`/bigeye-<any>`) exits the workflow.
- At any prompt, an issue display name alone is shorthand for "open that issue's action menu".
- Writes to state are batched: one commit at quit, plus one atomic write per delegated skill return (so crashes preserve progress).

### `/bigeye-table <name>`

**Argument grammar:**

| Invocation | Purpose |
|---|---|
| `/bigeye-table` | Use `last_table` from state; if empty, list top 5 recent in-scope tables |
| `/bigeye-table <name>` | Start loop for a named table (bare name or `schema.table` or `source.schema.table`) |
| `/bigeye-table <name> --profile <n>` / `--no-scope` / `--workspace <id>` | Standard global flags |

**Procedure:**

**Turn 1 — table status card + picker:**

1. Follow `preamble.md`.
2. Resolve the table name:
   - If `MCP_AVAILABLE=true`: use `mcp__bigeye-knowledgebase__search_metadata` or `mcp__bigeye__list_tables` to resolve name → `table_id` + fully-qualified name. Ambiguous → present a numbered picker, wait.
   - If `MCP_AVAILABLE=false`: accept only fully-qualified `source.schema.table`; bare name → print `Error / Fix / Why` pointing at `/bigeye-config verify` and stop. For the qualified form, resolve `table_id` via CLI `bigeye -w <profile> catalog get-table-info -sn <schema> -tn <table> -op "$TMPDIR"` and read the `id` field from the JSON.
3. Fetch table state in one batch:
   - Coverage % via `mcp__bigeye__get_table_dimension_coverage` (skipped with note if MCP off).
   - Open issues on the table via CLI (`issues get-issues -tid <id>` or post-filter).
   - Monitor count via CLI (`catalog get-metric-info -tid <id>`).
   - Local history from `state.json.tables[<fq>]`.
4. Render the table card (see mockup below).
5. Emit the picker prompt:

   ```
   Pick: [1] coverage, [2] improve, [3] deploy gaps, [4] open issue, [5] switch table, [q] quit
   > _
   ```

**Turn 2 — delegate:**

- `[1]` → delegate to `/bigeye-coverage <fq>`. Re-show card on return.
- `[2]` → delegate to `/bigeye-improve <fq>`. Re-show card on return.
- `[3]` → delegate to `/bigeye-deploy gaps` scoped to this table (pass scope flags internally).
- `[4]` → if issues listed, prompt for issue number; hand to `/bigeye-today` Turn 2 action menu for that issue.
- `[5]` → prompt `Table name: `, restart Turn 1 with the new name.
- `[q]` → persist state; emit footer.

**No-arg resume:** `/bigeye-table` with no name reads `last_table` from state:
- If set → start Turn 1 for it.
- If empty → list top 5 tables by `last_seen` from `state.json.tables`, filtered by active scope, as a picker.

---

## Output & UX

### Scope pill (every skill, line 1)

Format: `[<profile> · <workspace_id> · <non-empty-facets>]`

Examples:
- `[my-area · 42 · 3 tables]`
- `[my-area · 42 · 3 tables · 1 source]`
- `[my-area · 42 · NO-SCOPE]`
- `[my-area · 42 · 2/3 tables]` (unresolved: 1)

Rules:
- Omit facets whose count is zero.
- Single-line only; no prefix word, flush left.
- If scope has unresolved table names, append `(unresolved: "<name1>")` after the pill on the same line.

### Brief vs Full output

Every skill that renders a list of rows defaults to **Brief**: top `triage.default_brief_rows` (default 10) rows + summary. Unlock with `--full`. Override row count with `--limit N`.

Under Brief, after the displayed rows:
```
(<N more> — add --full to see all)
```
only when there actually are more rows.

`view.default_view = "full"` in `settings.json` makes every skill default to Full without needing the flag.

### Next / More footer

Every skill output ends with a 2-line block:

```
Next: <single best action, with the exact command inline>
More: <2-4 alternatives, · separated>
```

Examples:
- Triage: `Next: /bigeye-rca 10921     (top-scored, not yet investigated)`
- Coverage: `Next: /bigeye-deploy gaps --priority high     (3 high-priority gaps)`
- Deploy: `Next: /bigeye-triage     (verify in ~1 hour)`

Rules:
- `Next` is always a single command. Always include a parenthetical reason.
- `More` is 2–4 commands, `·` separated, no reasons. Skills pick the most likely alternates.

### Error format

Every user-facing error uses this 3-line block:

```
Error: <one-line cause>
Fix:   <exact command to run>
Why:   <one-line reason>
```

Under `--verbose`, append a block:

```
Details:
  command: <exact CLI that ran>
  stderr:  <full stderr>
  path:    <relevant file path>
```

### Progress indicators for multi-step skills

Long-running flows (`bigeye-improve` heavy mode, `bigeye-deploy` bigconfig plan+apply) print numbered progress on step transitions only:

```
[1/4] Fetching metrics ...
[2/4] Scoring heuristics ...
[3/4] Drafting SQL bundle ...
[4/4] Waiting for paste-back
```

No spinners. Transitions only.

### Interactive picker format

All picker prompts use the same shape:

```
Pick: [1-N], [a]ll, [q]uit
> _
```

Prompt arrow on its own line, instructions on the line above.

### Consistent argument syntax

Every SKILL.md `Arguments` section uses a single 3-column table:

| Invocation | Purpose | Example |

Global flags available in every skill: `--profile <name>`, `--no-scope`, `--workspace <id>`, `--full`, `--limit N`, `--verbose`. Documented once in `output.md`; skills don't repeat the description.

### Dashboard (`/bigeye`) layout

Non-interactive. One pass. Renders (in order):

1. Scope pill.
2. `## BigEye Dashboard — <weekday> <month> <day>, <HH:MM>`.
3. `Status:` line — open count, NEW count, cluster count (or `clusters: —` if MCP off), average coverage % across in-scope tables (`coverage: —` if MCP off).
4. `Last:` line — most recent activity from `state.json` (`/bigeye-today 14h ago  ·  /bigeye-rca #10921 4d ago`). If `state.json` is empty: one line `Last: no activity yet — run /bigeye-today to get started`.
5. `Open issues (top 5 by score):` — Brief-sized issue table with `History` column from `state.json`. Append `(N more — run /bigeye-today for full picker)` if truncated.
6. `Recently closed (last 7 days):` — up to 5 lines. Sourced from `state.json` entries whose `status_when_last_seen` is `CLOSED` and `last_seen` within 7 days. The plugin only sees issues it has touched — if an issue was closed outside Claude Code, it will not appear here. Section omitted if there are zero qualifying entries.
7. `Your tables:` — iterate the active profile's `table_ids` + resolved `table_names`. Per table: coverage % (via `mcp__bigeye__get_table_dimension_coverage`, or `—` if MCP off), open issue count (post-filtered from the issues already fetched in step 5's data call), last action from `state.json.tables[<fq>].actions[-1]`. If the profile has no table filters (only workspace + data-source scope), substitute a "Top tables (by activity)" section: the 5 most-recently-used tables from `state.json.tables` that fall inside the current scope. If the profile has no table filters and `state.json.tables` is empty, omit the section entirely.
8. `Commands:` — cheatsheet (stable across every run — ~10 lines).
9. `Next: / More:` footer.

Flags:
- `/bigeye --all` → ignore scope filters for the "Open issues" and "Your tables" sections; also expand to all state.json history.
- `/bigeye --profile <name>` → render with a different profile for this run.
- `/bigeye --no-scope` → same as today's flag; show the workspace-wide view.

Unrecognized trailing args → one-line hint before the dashboard: `Did you mean /bigeye-<x> <args>? /bigeye shows the dashboard; individual commands run tasks.`

---

## Per-skill tightening (atomic skills)

Each atomic SKILL.md is rewritten to:

1. Open with a 2–3 sentence "What this does" paragraph.
2. Link to `preamble.md` on a single line.
3. Use the 3-column argument table.
4. Include a procedure section (tightened from today's, but behaviorally equivalent).
5. End with a standardized "State-persistence" line that documents exactly what the skill writes to `state.json` on success.

The behaviors of atomic skills do **not** change except:

- **No-arg forms** on `bigeye-rca`, `bigeye-coverage`, `bigeye-improve` now read `state.json.last_issue` / `last_table` before prompting the user.
- **Error output** everywhere switches to the `Error / Fix / Why` block.
- **Footer** everywhere switches to the `Next: / More:` block.
- **Scope pill** replaces the dense `Scope:` line.
- **Brief default** with `--full` flag everywhere.

All internal CLI / MCP calls, scope application rules, and deploy confirmation gates are preserved unchanged.

---

## Agent changes

`agents/bigeye-morning-report.md`:

- Replaces its inline triage + cluster + coverage procedure with a single call to `/bigeye-today --report-only` (non-interactive), followed by coverage scoring (its current Step 3) and Slack notification (its current Step 5).
- Coverage and Slack logic stays in the agent; it's the only non-skill caller of those today.
- Slack settings read from `settings.json.slack` (not `conventions.md`).

---

## Output samples

### `/bigeye` dashboard

```
[my-area · 42 · 3 tables]
## BigEye Dashboard — Thu Apr 24, 09:12

Status:  12 open  ·  5 NEW  ·  2 clusters  ·  coverage 68% avg
Last:    /bigeye-today 14h ago  ·  /bigeye-rca #10921 4d ago

Open issues (top 5 by score):
 # | Issue | Score | Dim       | Table    | Column | Since | History
 1 | 10921 |  87   | Freshness | orders   | —      | 2h    | rca (4d)
 2 | 10923 |  73   | Validity  | orders   | email  | 1h    | —
 3 | 10918 |  61   | Volume    | payments | —      | 8h    | ack (6h)
 4 | 10925 |  58   | Validity  | orders   | status | 30m   | —
 5 | 10912 |  44   | Volume    | payments | —      | 2d    | ticket (1d)
 (7 more — run /bigeye-today for full picker)

Recently closed (last 7 days):
 - #10809 Freshness on orders (true-positive, 2d ago)
 - #10792 Validity on payments.email (false-positive, 4d ago)

Your tables:
 Table                              | Coverage | Open | Last action
 warehouse.public.orders            |  64%     |  3   | improve 3d ago
 warehouse.public.orders_audit      |  71%     |  0   | deploy 5d ago
 warehouse.public.payments          |  58%     |  2   | —

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

Next: /bigeye-today     (5 NEW issues waiting)
More: /bigeye-rca 10921  ·  /bigeye-table orders  ·  /bigeye-incidents auto
```

### `/bigeye-today` Turn 1

```
[my-area · 42 · 3 tables]
## Today — 12 open · 5 New · 4 Ack'd · 3 Monitoring · 2 clusters

 # | Issue | Score | Dim       | Table    | Column | Since | History
 1 | 10921 |  87   | Freshness | orders   | —      | 2h    | rca (4d)
 2 | 10923 |  73   | Validity  | orders   | email  | 1h    | —
 3 | 10918 |  61   | Volume    | payments | —      | 8h    | ack (6h)
 4 | 10925 |  58   | Validity  | orders   | status | 30m   | —
 5 | 10912 |  44   | Volume    | payments | —      | 2d    | ticket (1d)
 6 | 10905 |  39   | Validity  | orders   | region | 4h    | —
 7 | 10901 |  32   | Freshness | audit    | —      | 12h   | —
 8 | 10898 |  28   | Uniqueness| payments | id     | 1d    | —
 9 | 10895 |  22   | Volume    | orders   | —      | 1d    | —
10 | 10890 |  18   | Validity  | audit    | user   | 2d    | —
 (2 more — add --full to see all)

Pick: [1-12], [a]ll critical, [c]lusters, <display_name>, /<command>, [q]uit
> _
```

### `/bigeye-today` action menu (user typed `1`)

```
## Issue 10921 — Freshness on warehouse.public.orders
Since: 2h ago · Priority: High · Alerts: 3
History (local): rca (4d ago), incident (3d ago)
Upstream: orders_raw -> orders (from lineage cache)

[1] Root-cause analysis           (/bigeye-rca)
[2] Close                          (true-positive / false-positive / expected)
[3] Group with related             (/bigeye-incidents auto)
[4] Draft a ticket                 (/bigeye-ticket)
[5] Back to issue list
[q] Quit

> _
```

### `/bigeye-table orders` Turn 1

```
[my-area · 42]
## Table — warehouse.public.orders
Coverage: 64% · 14 monitors · 3 open issues · last deploy: 3 monitors (5d ago)

Open issues on this table:
 # | Issue | Dim       | Column | Since
 1 | 10921 | Freshness | —      | 2h
 2 | 10923 | Validity  | email  | 1h
 3 | 10925 | Validity  | status | 30m

[1] Coverage report               (/bigeye-coverage)
[2] Improve monitors              (/bigeye-improve)
[3] Deploy gaps                   (/bigeye-deploy gaps)
[4] Open issue                    (1, 2, or 3 above)
[5] Switch table
[q] Quit

> _
```

### Brief triage output (atomic `/bigeye-triage`)

```
[my-area · 42 · 3 tables]
## BigEye Triage — Thu Apr 24

### New (5)
 # | Issue | Score | Dim       | Table    | Column | Since | History
 1 | 10921 |  87   | Freshness | orders   | —      | 2h    | rca (4d)
 2 | 10923 |  73   | Validity  | orders   | email  | 1h    | —
 ...

### Ack'd (4)
 # | Issue | Score | Dim       | Table    | Column | Since | History
 ...

### Monitoring (3)
 # | Issue | Score | Dim       | Table    | Column | Since | History
 ...

Summary: 5 new · 4 ack'd · 3 monitoring · 2 clusters

Next: /bigeye-rca 10921     (top-scored, not yet investigated)
More: /bigeye-today  ·  /bigeye-incidents auto  ·  /bigeye  (dashboard)
```

### Error example

```
Error: BigEye CLI auth not configured.
Fix:   /bigeye-config init
Why:   No ~/.bigeye/credentials file found.
```

---

## Migration

### On-disk migration

| File | Action |
|---|---|
| `profiles.json` | None — unchanged schema |
| `ticket-templates/*.md` | None |
| `~/.bigeye/config.ini`, `~/.bigeye/credentials` | None |
| `settings.json` | Seeded on first run post-upgrade with the defaults above. One-line notice: `Wrote ~/.claude/bigeye-plugin/settings.json with defaults — edit via /bigeye-config settings.` |
| `state.json` | Created empty on first workflow write |

### First-run-after-upgrade notice

On the first skill invocation after the upgrade, after preamble but before the skill's own output:

```
Upgraded to bigeye-plugin 0.4.0. New: /bigeye (dashboard), /bigeye-today, /bigeye-table.
Your profiles and templates are preserved. See README or run /bigeye for a tour.
```

Detected by: `settings.json._meta.upgrade_seen == false`. Flip to `true` after printing. Prints exactly once.

### Command-surface compatibility

No command is renamed or removed. Muscle memory is preserved. The single behavior change on the surface:

- `/bigeye <free text>` used to route to a sub-skill by intent. After upgrade, `/bigeye` is the dashboard. Free-text input prints a one-line hint (`Did you mean /bigeye-<x>?`) above the dashboard.

### Conventions.md customizations

If the user edited the old `conventions.md` for their Slack channel or thresholds, those edits are lost in the upgrade — the new location is `settings.json`. No automatic migration (solo-maintainer context; detection not worth the complexity). Release notes call this out explicitly.

### Version bump

`plugin.json.version`: `0.3.0` → `0.4.0`.

### README

Rewritten to lead with the two workflow commands + dashboard. Moves the full command table below. Adds a "What changed in 0.4.0" section.

---

## Rollout sequence

Each step is independently shippable. Safe to pause between any two.

1. **Preamble + output refs + settings file.** Write `preamble.md` (merging scope.md + cli.md), `output.md` (formatting only — no config), and wire `settings.json` seeding into preamble Step 1 so any skill that runs has config available. Add `/bigeye-config settings show|edit <key>`. Do not delete the old reference files yet; leave them as one-line stubs pointing at the new files.
2. **Atomic skill rewrites.** Retarget each atomic SKILL.md to `preamble.md` + `output.md`. Reads that used to hit `conventions.md` for Slack/severity/thresholds now hit `settings.json`. Standardize argument tables, scope pill, Brief/Full, footer, error format. Verify every atomic skill still produces equivalent output (minus the new formatting) on real inputs with MCP on and off.
3. **State file + state writes.** Define the schema; add the append-and-prune routine to preamble Step 8; wire every atomic skill to persist on success. Wire no-arg forms of `rca`/`coverage`/`improve` to read `last_issue`/`last_table`. Verify by running each atomic skill and checking `state.json`.
4. **Dashboard `/bigeye`.** Rewrite `bigeye/SKILL.md` as the dashboard. Drop the intent-routing table. Wire the `Did you mean` hint for unrecognized args. Footer/cheatsheet text can reference `/bigeye-today` and `/bigeye-table` even before they exist — those are just strings.
5. **`/bigeye-today` workflow.** Build from scratch. Delegates to atomic skills; does not duplicate their logic.
6. **`/bigeye-table` workflow.** Same pattern.
7. **Agent retarget.** `bigeye-morning-report` calls `/bigeye-today --report-only`. Slack config reads from `settings.json.slack`.
8. **Release polish.** Bump version, update README, write the upgrade notice logic, finalize the old-reference-docs removal (delete `scope.md` and `cli.md`; `conventions.md` removed outright unless anything outside the repo links to it — then leave a stub).

---

## Verification

Verification is manual (these are markdown skills, not code with unit tests). For each rollout step, the check is:

1. **Preamble + output refs + settings:** `preamble.md` is the only file referenced by any atomic skill's preamble block. `/bigeye-config settings show` prints the seeded defaults. Editing via `/bigeye-config settings edit slack.channel '#test'` updates the JSON.
2. **Atomic skill rewrites:** run each atomic skill against a live workspace with MCP on — confirm output shape matches the mockups above (scope pill, Brief, Next/More footer, new error format). Run each with MCP off — confirm graceful degradation (no crashes, correct warning template, hard-fails only on documented paths).
3. **State file:** after running `/bigeye-rca 10921`, `state.json.last_issue == "10921"` and `state.json.issues["10921"].actions[-1].skill == "bigeye-rca"`. Running `/bigeye-rca` with no args picks up `10921`. Pruning caps apply: inject > 500 fake issue entries and confirm the oldest get dropped after a skill run.
4. **Dashboard:** prints the mockup layout with live data; truncation markers appear correctly; `/bigeye --all` widens the view; `/bigeye frobnicate` prints the "Did you mean" hint before the dashboard.
5. **`/bigeye-today`:** full reactive flow (list → pick → RCA → return to action menu → quit) works end-to-end. `--report-only` produces the same Turn 1 output without prompting. Typing a slash command at any prompt exits the workflow.
6. **`/bigeye-table <name>`:** full proactive flow works end-to-end. No-arg form picks up `last_table`; with empty state it shows the recent-tables picker. Bare name works with MCP on, fully-qualified name works with MCP off.
7. **Agent:** scheduled run still produces the Slack message and terminal report. Slack channel honors the edited `settings.json.slack.channel`.
8. **Release:** first invocation after upgrading prints the notice exactly once; second invocation does not. `plugin.json.version == "0.4.0"`. README leads with the new workflows.

---

## Risks

| Risk | Mitigation |
|---|---|
| Workflow skills are chatty and expensive (multiple turns × preamble reads) | Preamble reads are already required in every atomic skill; workflow re-reads once per turn, same cost. State.json reduces the "which issue were we on?" cost. If it's still too heavy, we can cache the issue-list JSON across turns under `$TMPDIR`. |
| State.json can bloat if the user has many profiles / long history | Hard caps: 500 issues + 100 tables, LRU by `last_seen`. Settings pattern supports tightening later. |
| Users confused by `/bigeye` now being a dashboard | `Did you mean` hint above the dashboard on unrecognized args. One-time upgrade notice. README rewrite. |
| New Brief-by-default hides information power users rely on | `view.default_view="full"` in settings for one-time opt-out. `--full` per invocation. |
| Lost Slack/threshold customizations in `conventions.md` | Release notes call this out. Solo-maintainer context makes automatic migration overkill. |

---

## Open questions

None. All four final-pass questions (default_view, conventions migration detection, version bump, missing items) were resolved: include `default_view`, no auto-migration, bump to 0.4.0, nothing else missing.
