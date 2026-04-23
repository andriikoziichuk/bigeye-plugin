---
name: bigeye-triage
description: Use when the user wants to see active BigEye issues, asks what's broken or on fire, or needs a prioritized view of data quality problems
user-invocable: true
---

# BigEye Triage

Answers "what's on fire?" — fetches all active issues and presents them prioritized by severity.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for severity classification rules and output formatting, `skills/bigeye/references/scope.md` for how to load and apply the active scope profile, and `skills/bigeye/references/cli.md` for CLI invocation rules and MCP-availability detection.

## Arguments

Parse `$ARGUMENTS` (space-separated):
- Empty or no args: show all open issues (NEW + ACKNOWLEDGED + MONITORING)
- `new`: only NEW status issues (unacknowledged)
- `24h`: issues opened in the last 24 hours only
- A number like `50`: override max_issues limit

## Procedure

### Step 0: Load Scope

Follow `skills/bigeye/references/scope.md` (Steps A–E) to load the active profile. Parse and honor `--profile <name>`, `--no-scope`, and `--workspace <id>` flags from `$ARGUMENTS` before parsing the skill's own arguments. Then follow `cli.md` Step B to detect MCP availability (sets `MCP_AVAILABLE`).

### Step 1: Fetch Active Issues

Use CLI per `cli.md` Step C:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> issues get-issues \
  {if data_source_ids non-empty: for each id, append `-wid <id>`} \
  {if schema_names non-empty: for each name, append `-sn <name>`} \
  -op "$TMPDIR"
```

Parse each JSON file in `$TMPDIR`. Filter in-memory:
- Keep only issues whose `status` is `ISSUE_STATUS_NEW`, `ISSUE_STATUS_ACKNOWLEDGED`, or `ISSUE_STATUS_MONITORING`.
- If the `new` argument was supplied, keep only `ISSUE_STATUS_NEW`.
- If the `24h` argument was supplied, keep only issues with `openedAt` within the last 24 hours.
- **Table filter (profile-driven):** build `effective_table_ids = union(profile.table_ids, resolved(profile.table_names))`. If `effective_table_ids` is non-empty, keep only issues whose `metricMetadata.datasetId` is in that set. The `bigeye issues get-issues` CLI does not accept a table flag, so this filter MUST be applied post-fetch or tables outside scope will leak into the output.
- Cap at `max_issues` (50 by default, or the user's override).

If the filtered list is empty, print the empty-result message per `scope.md` Step H and stop.

Note: the CLI has no `--tag` filter; scope tags are no longer supported.
Note: when MCP is unavailable, `table_names` cannot be resolved to IDs — the skill MUST print a one-line warning listing unresolved names, then fall back to `effective_table_ids = profile.table_ids` alone. Issues on those named-but-unresolved tables will leak through unless the user also lists the IDs explicitly.

### Step 2: Detect Issue Clusters

If `MCP_AVAILABLE=true`:
  For each open issue, call `mcp__bigeye__list_related_issues` with `starting_issue_id: <issue_id>`. Count related issues per issue. Flag any with 2+ related as a cluster.

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=cluster detection`. Set `cluster_count=null` for the output. Do not call MCP.

### Step 3: Format Output

Group issues by `currentStatus` — one section per status bucket (New / Ack'd / Monitoring). Sort rows within each bucket by `priorityScore` descending. Severity classification (`conventions.md`) is **not** rendered here — status grouping replaces it for triage.

```
Scope: {per scope.md Step G}

## BigEye Triage — {today's date}

### New ({count} issues)
| # | Issue | Score | Dim | Table | Column | Metric (type) | Since | Alerts | First run |
|---|-------|-------|-----|-------|--------|---------------|-------|--------|-----------|
| 1 | {display_name} | {priorityScore} | {dimension} | {tableName} | {columnName or "—"} | {metricName} ({metricType}) | {time_ago} | {alertCount} | {firstMetricRunStatus short form} |

### Ack'd ({count} issues)
| # | Issue | Score | Dim | Table | Column | Metric (type) | Since | Alerts | First run |
|---|-------|-------|-----|-------|--------|---------------|-------|--------|-----------|

### Monitoring ({count} issues)
| # | Issue | Score | Dim | Table | Column | Metric (type) | Since | Alerts | First run |
|---|-------|-------|-----|-------|--------|---------------|-------|--------|-----------|

### Summary
- {new_count} new, {ackd_count} ack'd, {monitoring_count} monitoring
- {cluster_count} issue clusters detected (potential shared root cause)
- Suggested next: `/bigeye-rca {top_issue_by_score}` for the highest-scored issue (any status)
```

Column sourcing:
- **Score** — `priorityScore` (0–100 from BigEye)
- **Dim** — `metricConfiguration.dimension.displayName`
- **Table** — `metricMetadata.datasetName`
- **Column** — `metricMetadata.fieldName` or `—` for table-level metrics
- **Metric (type)** — `metricConfiguration.name` then the metric type in parentheses: prefer `metricConfiguration.metricType.predefinedMetric.metricName`; fall back to `metricConfiguration.metricType.templateMetric.aggregationType`; else `—`
- **Alerts** — `alertCount`
- **First run** — `firstMetricRunStatus` with the `METRIC_RUN_STATUS_` prefix stripped (e.g. `LOWERBOUND_CRITICAL`, `GROUPS_CRITICAL`). For `GROUPS_CRITICAL`, append `(N/M)` when the summary exposes the ratio.

If a status section has 0 issues, omit that section entirely. Status order is always New → Ack'd → Monitoring.

If `cluster_count` is null (MCP absent), replace the `{cluster_count} issue clusters detected (potential shared root cause)` line in the Summary with: `Cluster detection disabled — MCP not configured (see bigeye-mcp-install.md).`

### Step 4: Suggest Next Actions

Always end with:
- If clusters detected: "Run `/bigeye-incidents auto` to group related issues"
- Highest-scored open issue (any status): "Run `/bigeye-rca {issue}` for root cause analysis"
- If many NEW issues: "Run `/bigeye-incidents auto` then acknowledge clusters"
- Stale Monitoring/Ack'd issues with high alert counts: consider closing via `bigeye issues update-issue -cl FALSE_POSITIVE|EXPECTED`
- For any issue you want to hand to a data vendor: `/bigeye-ticket <display_name>`
