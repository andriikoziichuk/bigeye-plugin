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
