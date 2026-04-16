---
name: bigeye-rca
description: Use when the user wants to investigate why a BigEye issue is happening, trace root causes through lineage, or debug a specific data quality problem
user-invocable: true
---

# BigEye Root Cause Analysis

Answers "why is this broken?" — traces an issue through data lineage to find the upstream root cause.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for severity classification and output formatting.

## Arguments

Parse `$ARGUMENTS`:
- A number (e.g., `10921`): issue display name to investigate
- Empty: run a lightweight triage to find the top critical issue and investigate that

## Procedure

### Step 1: Resolve the Issue

**If an issue number was provided:**
1. Call `mcp__bigeye__search_issues` with `name_query: "{number}"`
2. If no match, tell the user and suggest they check the issue number
3. If multiple matches, list them and ask which one
4. Extract the `id` field (internal ID) from the match

**If no argument provided:**
1. Call `mcp__bigeye__list_issues` with `statuses: ["ISSUE_STATUS_NEW"]`, `max_issues: 5`, `compact: false`
2. Apply severity classification from conventions.md
3. Pick the top Critical issue (or top Warning if no Critical)
4. Tell the user which issue was auto-selected and why

### Step 2: Get Full Issue Details

Call `mcp__bigeye__get_issue` with `issue_id: {internal_id}`.

Extract and note:
- Metric type (what kind of check failed)
- Table and column affected
- When it started (first event timestamp)
- Current status
- Event history (how it evolved)

### Step 3: Trace Lineage

Call `mcp__bigeye__get_issue_lineage_trace` with:
- `issue_id: {internal_id}`
- `include_root_cause_analysis: true`
- `include_impact_analysis: true`
- `max_depth: 5`

From the result, identify:
- The upstream path from the issue to its root cause
- Whether a root cause node was identified
- Downstream impact (how many tables/columns affected)

### Step 4: Get Related Issues

Call `mcp__bigeye__list_related_issues` with `starting_issue_id: {internal_id}`.

Note which related issues have `isRootCause: true`.

### Step 5: Get Resolution Steps

Call `mcp__bigeye__get_resolution_steps` with `issue_id: {internal_id}`.

### Step 6: Format Output

```
## Root Cause Analysis — Issue #{display_name}

### Issue
{metric_type} failed on {table_name}
Column: {column_name or "table-level"}
Status: {status_display} | Since: {time_since} | Priority: {priority_display}

### Lineage Trace
{upstream_node_1} -> {upstream_node_2} -> ... -> {issue_table}
                     ^ ROOT CAUSE HERE
{Describe what the lineage trace reveals. If a root cause node was identified,
highlight it prominently. If upstream issues exist, name them.}

### Related Issues (same root cause)
| Issue | Dimension | Table | Root Cause? |
|-------|-----------|-------|-------------|
| {display_name} | {dimension} | {table} | {yes/no} |

{If no related issues, say "No related issues found — this appears to be an isolated issue."}

### Resolution Steps
{numbered list from get_resolution_steps}

### Suggested Actions
{If 2+ related issues:}
- Group into incident: `/bigeye-incidents {issue_ids_space_separated}`
{Always:}
- Acknowledge this issue: updates status to ACKNOWLEDGED
- Close as resolved: `/bigeye-incidents close {display_name} --label true-negative`
{If root cause is upstream:}
- Investigate upstream root cause: `/bigeye-rca {root_cause_issue_number}`
```
