---
name: bigeye
description: Internal — invoked only when explicitly typed as `/bigeye`. Do not auto-suggest. The user-facing surface in v0.5 is `/bigeye-roster`, `/bigeye-improve`, `/bigeye-coverage`, `/bigeye-config`.
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
