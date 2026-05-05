---
name: bigeye-table
description: Internal — table audit helper invoked only when explicitly typed as `/bigeye-table`. Do not auto-suggest. Use `/bigeye-coverage <table>` and `/bigeye-improve <monitor_id>` instead.
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
