---
name: bigeye-rca
description: Internal — root-cause-analysis helper invoked only when explicitly typed as `/bigeye-rca`. Do not auto-suggest. Roster recommends `improve` or `ticket` instead.
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
