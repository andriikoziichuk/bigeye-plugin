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
- Empty or no args: show all open issues (NEW + ACKNOWLEDGED)
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
- Keep only issues whose `status` is `ISSUE_STATUS_NEW` or `ISSUE_STATUS_ACKNOWLEDGED`.
- If the `new` argument was supplied, keep only `ISSUE_STATUS_NEW`.
- If the `24h` argument was supplied, keep only issues with `openedAt` within the last 24 hours.
- Cap at `max_issues` (50 by default, or the user's override).

If the filtered list is empty, print the empty-result message per `scope.md` Step H and stop.

Note: the CLI has no `--tag` filter; scope tags are no longer supported.

### Step 2: Classify Severity

For each issue, apply the severity rules from conventions.md:

**Critical:**
- Dimension is Freshness or Volume (pipeline reliability)
- Issue is older than 4 hours and still NEW
- Issue has 3+ related issues

**Warning:**
- Dimension is Validity, Completeness, or Uniqueness
- Issue has 1-2 related issues
- Issue is ACKNOWLEDGED but older than 24 hours

**Low:**
- Recently opened (< 1 hour) with no related issues
- Distribution or Format dimension
- Already in MONITORING status

### Step 3: Detect Issue Clusters

If `MCP_AVAILABLE=true`:
  For each Critical and Warning issue, call `mcp__bigeye__list_related_issues` with `starting_issue_id: <issue_id>`. Count related issues per issue. Flag any with 2+ related as a cluster.

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=cluster detection`. Set `cluster_count=null` for the output. Do not call MCP.

### Step 4: Format Output

Use this exact format:

```
Scope: {per scope.md Step G}

## BigEye Triage — {today's date}

### Critical ({count} issues)
| # | Issue | Dimension | Column | Since | Related |
|---|-------|-----------|--------|-------|---------|
| 1 | {display_name} | {dimension} | {column or "—"} | {time_ago} | {related_count} related |

### Warning ({count} issues)
| # | Issue | Dimension | Column | Since | Related |
|---|-------|-----------|--------|-------|---------|

### Low ({count} issues)
| # | Issue | Dimension | Column | Since | Related |
|---|-------|-----------|--------|-------|---------|

### Summary
- {critical} critical, {warning} warning, {low} low
- {cluster_count} issue clusters detected (potential shared root cause)
- Suggested next: `/bigeye-rca {top_critical_issue}` for the top critical issue
```

If a severity section has 0 issues, omit that section entirely.

If `cluster_count` is null (MCP absent), replace the `{cluster_count} issue clusters detected (potential shared root cause)` line in the Summary with: `Cluster detection disabled — MCP not configured (see bigeye-mcp-install.md).`

### Step 5: Suggest Next Actions

Always end with:
- If clusters detected: "Run `/bigeye-incidents auto` to group related issues"
- Top critical issue: "Run `/bigeye-rca {issue}` for root cause analysis"
- If many NEW issues: "Run `/bigeye-incidents auto` then acknowledge clusters"
