---
name: bigeye-rca
description: Use when the user wants to investigate why a BigEye issue is happening, trace root causes through lineage, or debug a specific data quality problem
user-invocable: true
---

# BigEye Root Cause Analysis

Answers "why is this broken?" — traces an issue through data lineage to find the upstream root cause.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for severity classification and output formatting, and `skills/bigeye/references/scope.md` for how to load and apply the active scope profile, and skills/bigeye/references/cli.md for CLI invocation rules and MCP-availability detection.

**RCA special case:** primary issue lookup by ID is ALWAYS unscoped (the user named a specific issue). Scope applies only to the lineage expansion and related-issue search in Steps 3–4. See scope.md Step I for the out-of-scope soft-notice text.

## Arguments

Parse `$ARGUMENTS`:
- A number (e.g., `10921`): issue display name to investigate
- Empty: run a lightweight triage to find the top critical issue and investigate that
- `--internal-id`: treat the numeric argument as an internal ID instead of a display name. Skips the MCP display-name lookup. Required when MCP is unavailable.

## Procedure

### Step 0: Load Scope

Follow `skills/bigeye/references/scope.md` (Steps A–E) to load the active profile. Parse `--profile <name>`, `--no-scope`, and `--workspace <id>` from `$ARGUMENTS` before parsing the skill's own arguments. Then follow cli.md Step B to detect MCP availability (sets MCP_AVAILABLE).

RCA reminder: the primary issue lookup in Step 1 ignores scope. Scope applies to Steps 3 (lineage expansion) and 4 (related issues only).

### Step 1: Resolve the Issue

Parse the argument:
- If `--internal-id` was provided, treat the number as an internal ID directly; set `internal_id={number}`. Skip the MCP lookup.
- If no argument was provided, run the fallback described below (auto-select top critical).
- Otherwise the number is a display name; must be resolved via MCP.

**Display-name → internal-ID lookup (MCP required):**

If `MCP_AVAILABLE=true`:
  Call `mcp__bigeye__search_issues` with `name_query: "{number}"`. If no match, tell the user and stop. If multiple, list and ask which. Extract `id` (internal ID).

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=display-name lookup` and `{CLI-only workaround}=Re-run with --internal-id <internal-id> (find the internal ID in the Bigeye UI URL: app.bigeye.com/issue/<internal-id>)`. Stop the skill — there's nothing useful to show without an internal ID.

**If no argument was provided (auto-select):**

Use the CLI per `cli.md` Step C to fetch the 5 most recent NEW issues:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> issues get-issues -op "$TMPDIR"
```

Read the JSON files, filter to `ISSUE_STATUS_NEW`, apply severity per `conventions.md`, pick the top Critical (or top Warning if no Critical). Use that issue's `id` as `internal_id`. Tell the user which issue was auto-selected and why.

### Step 2: Get Full Issue Details

Use CLI per `cli.md` Step C:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> issues get-issues -iid <internal_id> -op "$TMPDIR"
```

Read the single JSON file. Extract and note:
- Metric type (`metricConfiguration.metricType`)
- Table (`tableName`) and column (`columnName`)
- When started (`openedAt` — first event timestamp in `events[]`)
- Current status (`status`)
- Event history (`events[]`)

### Step 3: Trace Lineage

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=lineage trace`. Skip this step. Proceed to the next.

If `MCP_AVAILABLE=true`:
  Call `mcp__bigeye__get_issue_lineage_trace` with:
  - `issue_id: {internal_id}`
  - `include_root_cause_analysis: true`
  - `include_impact_analysis: true`
  - `max_depth: 5`
  - Plus non-empty scope parameters from Step 0 if the tool's schema accepts them; otherwise post-filter the returned nodes/edges to the in-scope tables only.

  From the result, identify:
  - The upstream path from the issue to its root cause
  - Whether a root cause node was identified
  - Downstream impact (how many tables/columns affected)

### Step 4: Get Related Issues

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=related issues`. Skip this step. Proceed to the next.

If `MCP_AVAILABLE=true`:
  Call `mcp__bigeye__list_related_issues` with `starting_issue_id: {internal_id}`.

  Filter the returned list to only include issues whose table/data_source falls inside the working profile (per Step 0 map). Do not apply this filter under `--no-scope`.

  Note which related issues have `isRootCause: true`.

### Step 5: Get Resolution Steps

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=resolution steps`. Skip this step. Proceed to the next.

If `MCP_AVAILABLE=true`:
  Call `mcp__bigeye__get_resolution_steps` with `issue_id: {internal_id}`.

### Step 6: Format Output

If any MCP step (3, 4, or 5) was skipped, insert this line immediately after the Scope: header, before the `## Root Cause Analysis — Issue #{...}` heading:

```
Reduced RCA — MCP unavailable. Lineage, related issues, and/or resolution steps omitted. See bigeye-mcp-install.md.
```

For any MCP section that was skipped (Lineage Trace, Related Issues, Resolution Steps), replace its body with the single line: `(skipped — MCP unavailable)`.

```
Scope: {per scope.md Step G}
{If the primary issue is outside the working scope, insert the soft notice from scope.md Step I on the next line.}

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
