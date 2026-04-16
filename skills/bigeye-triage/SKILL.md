---
name: bigeye-triage
description: Use when the user wants to see active BigEye issues, asks what's broken or on fire, or needs a prioritized view of data quality problems
user-invocable: true
---

# BigEye Triage

Answers "what's on fire?" — fetches all active issues and presents them prioritized by severity.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for severity classification rules and output formatting, and `skills/bigeye/references/scope.md` for how to load and apply the active scope profile.

## Arguments

Parse `$ARGUMENTS` (space-separated):
- Empty or no args: show all open issues (NEW + ACKNOWLEDGED)
- `new`: only NEW status issues (unacknowledged)
- `24h`: issues opened in the last 24 hours only
- A number like `50`: override max_issues limit

## Procedure

### Step 0: Load Scope

Follow `skills/bigeye/references/scope.md` (Steps A–E) to load the active profile and build the parameter map. Parse and honor `--profile <name>`, `--no-scope`, and `--workspace <id>` flags from `$ARGUMENTS` before parsing the skill's own arguments.

### Step 1: Fetch Active Issues

Call `mcp__bigeye__list_issues` with:
- `statuses`: `["ISSUE_STATUS_NEW", "ISSUE_STATUS_ACKNOWLEDGED"]`
  - If argument is `new`, use only `["ISSUE_STATUS_NEW"]`
- `compact`: `false` (we need metric info for severity classification)
- `max_issues`: `50` (or user-specified override)
- Plus every non-empty scope parameter from the Step 0 map (`workspace_id`, `data_source_ids`, `table_ids`, `schema_names`, `tags`).

If no issues returned, print the empty-result message per scope.md Step H (`No active issues in scope '{profile}' — all clear.` or `No active issues — all clear.` under `--no-scope`) and stop.

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

For each Critical and Warning issue, call `mcp__bigeye__list_related_issues` with `starting_issue_id: <issue_id>`.

Count related issues per issue. If any issue has 2+ related issues, flag it as a cluster.

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

### Step 5: Suggest Next Actions

Always end with:
- If clusters detected: "Run `/bigeye-incidents auto` to group related issues"
- Top critical issue: "Run `/bigeye-rca {issue}` for root cause analysis"
- If many NEW issues: "Run `/bigeye-incidents auto` then acknowledge clusters"
