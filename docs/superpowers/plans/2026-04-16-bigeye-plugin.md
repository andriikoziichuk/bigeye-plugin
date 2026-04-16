# BigEye Data Observability Plugin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code plugin with 6 skills (hub + 5 workflows), 1 scheduled agent, shared conventions, and hooks — all powered by the BigEye MCP server.

**Architecture:** Pure markdown plugin (no code dependencies). Skills instruct Claude how to call BigEye MCP tools and format output. A hub skill routes natural language; sub-skills handle triage, RCA, coverage, deployment, and incidents. A scheduled agent composes them for daily reports with Slack notifications.

**Tech Stack:** Claude Code plugin system (SKILL.md, agents, hooks.json), BigEye MCP server, Slack MCP server

---

## File Map

| File | Responsibility |
|------|---------------|
| `.claude-plugin/plugin.json` | Plugin manifest — name, version, paths to skills/agents/hooks |
| `skills/bigeye/SKILL.md` | Hub skill — routes natural language to sub-skills, auto-triggers |
| `skills/bigeye/references/conventions.md` | Shared formatting, severity logic, status mapping, Slack templates |
| `skills/bigeye-triage/SKILL.md` | Triage skill — prioritized active issues view |
| `skills/bigeye-rca/SKILL.md` | RCA skill — lineage-traced root cause analysis |
| `skills/bigeye-coverage/SKILL.md` | Coverage skill — dimension/column gap analysis |
| `skills/bigeye-deploy/SKILL.md` | Deploy skill — bulk monitor creation with confirmation |
| `skills/bigeye-incidents/SKILL.md` | Incidents skill — group related issues, manage incidents |
| `agents/bigeye-morning-report.md` | Scheduled agent — daily summary + Slack notification |
| `hooks/hooks.json` | Auto-trigger hooks for session start and BigEye context |
| `README.md` | Installation and usage guide |

---

### Task 1: Plugin Manifest & Directory Scaffold

**Files:**
- Create: `.claude-plugin/plugin.json`

- [ ] **Step 1: Create the plugin manifest**

Create `.claude-plugin/plugin.json`:

```json
{
  "name": "bigeye",
  "displayName": "BigEye Data Observability",
  "description": "Skills and agents for managing BigEye monitoring at scale — triage, root cause analysis, coverage gaps, bulk monitor deployment, and incident management.",
  "version": "0.1.0",
  "author": { "name": "Andrii Koziichuk" },
  "skills": "./skills/",
  "agents": "./agents/",
  "hooks": "./hooks/hooks.json"
}
```

- [ ] **Step 2: Create all directories**

```bash
mkdir -p .claude-plugin
mkdir -p skills/bigeye/references
mkdir -p skills/bigeye-triage
mkdir -p skills/bigeye-rca
mkdir -p skills/bigeye-coverage
mkdir -p skills/bigeye-deploy
mkdir -p skills/bigeye-incidents
mkdir -p agents
mkdir -p hooks
```

- [ ] **Step 3: Verify structure**

```bash
find . -type d -not -path './.venv/*' -not -path './.idea/*' | sort
```

Expected output should show all directories listed above.

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "feat: add plugin manifest and directory scaffold"
```

---

### Task 2: Shared Conventions Reference

**Files:**
- Create: `skills/bigeye/references/conventions.md`

This file is depended on by every other skill, so it must be created first.

- [ ] **Step 1: Create the conventions file**

Create `skills/bigeye/references/conventions.md`:

```markdown
# BigEye Plugin — Shared Conventions

All BigEye skills MUST read and follow these conventions for consistent output.

---

## Status Display Mapping

| API Status | Display |
|------------|---------|
| ISSUE_STATUS_NEW | New |
| ISSUE_STATUS_ACKNOWLEDGED | Ack'd |
| ISSUE_STATUS_CLOSED | Closed |
| ISSUE_STATUS_MONITORING | Monitoring |
| ISSUE_STATUS_MERGED | Merged |

## Severity Classification

Classify every issue into one of three severity levels:

**Critical:**
- Freshness or Volume dimension issues (pipeline is broken)
- Any issue older than 4 hours still in NEW status
- Any issue with 3+ related downstream issues

**Warning:**
- Data quality dimension issues: Validity, Completeness, Uniqueness
- Issues with 1-2 related downstream issues
- Issues in ACKNOWLEDGED status that are older than 24 hours

**Low:**
- Recently opened issues (< 1 hour) with no related issues
- Distribution or Format dimension issues with no downstream impact
- Issues already in MONITORING status

## Output Formatting

### Issue Tables

Always use this column format for issue listings:

```
| # | Issue | Dimension | Column | Since | Related |
|---|-------|-----------|--------|-------|---------|
| 1 | 10921 | Freshness | — | 2h ago | 2 related |
```

- **#**: Sequential row number
- **Issue**: Display name (the number shown in BigEye UI)
- **Dimension**: The data quality dimension (Freshness, Volume, Validity, etc.)
- **Column**: Column name, or "—" for table-level metrics
- **Since**: Human-readable time since issue opened (e.g., "2h ago", "3d ago")
- **Related**: Count of related issues, or "—" if none

### Severity Indicators

Use these prefixes in summary text:
- Critical issues: no emoji, just bold **Critical**
- Warning issues: **Warning**
- Low issues: **Low**

Do NOT use emoji unless the user explicitly requests it.

### Chaining Suggestions

Every skill output MUST end with a "Suggested next" section pointing to the logical next skill:
- Triage → suggest `/bigeye-rca <top-issue>`
- RCA → suggest `/bigeye-incidents` if multiple related issues, or acknowledge
- Coverage → suggest `/bigeye-deploy gaps`
- Deploy → suggest `/bigeye-triage` to verify monitors collecting data
- Incidents → suggest `/bigeye-rca <root-cause>` for deep dive

## MCP Tool Patterns

### Issue Name Resolution

When the user provides an issue number (display name like "10921"):
1. Call `mcp__bigeye__search_issues` with `name_query: "<number>"`
2. Use the `id` field from the result for all subsequent API calls
3. If multiple matches, ask the user to clarify

### Pagination

When calling `list_issues` or other paginated tools:
1. Start with default page_size (20)
2. If `page_cursor` is returned in result, fetch next page
3. Continue until no more pages or `max_issues` reached
4. For triage, default `max_issues: 50` to avoid context overload

### Error Recovery

If an MCP tool call fails:
1. Report the error clearly to the user
2. Suggest the most likely cause (wrong ID, table not found, permissions)
3. Offer to retry with corrected parameters
4. Never silently skip failures

## Slack Notification Templates

### Configuration

Slack settings (edit these values for your team):
- **Channel**: `#data-quality-alerts`
- **Severity threshold**: Only notify on Critical issues
- **Mention group**: `@data-oncall` for Critical issues
- **MCP tool**: Use `mcp__claude_ai_Slack__*` tools (requires authentication)

### Morning Report Template

```
BigEye Morning Report — {date}

{critical_count} critical | {warning_count} warning | {low_count} low

Top issues:
{top_3_issues_one_line_each}

Coverage: {coverage_percent}%
Run /bigeye-triage in Claude Code for details
```

If critical_count > 0, prepend with `@data-oncall` mention.

### Alert Template (for ad-hoc critical alerts)

```
BigEye Alert — {issue_display_name}
{dimension} issue on {table_name}.{column_name}
Since: {time_since}
Related: {related_count} issues
```

## Tag Conventions

- `deployed-by-plugin`: Applied to all monitors created via `/bigeye-deploy`. Used for tracking and auditing plugin-created monitors.
- Before tagging, call `mcp__bigeye__list_tags` with `search: "deployed-by-plugin"` to check if tag exists.
- If not found, create it with `mcp__bigeye__create_tag` with `name: "deployed-by-plugin"`, `color_hex: "#6366F1"`.

## Priority Mapping

| BigEye Priority | Display |
|----------------|---------|
| ISSUE_PRIORITY_LOW | Low |
| ISSUE_PRIORITY_MED | Medium |
| ISSUE_PRIORITY_HIGH | High |

## Closing Labels

When closing issues, use one of:
- `METRIC_RUN_LABEL_TRUE_NEGATIVE`: Real issue, now resolved
- `METRIC_RUN_LABEL_FALSE_POSITIVE`: Not a real issue (noisy monitor)
```

- [ ] **Step 2: Verify the file reads correctly**

```bash
wc -l skills/bigeye/references/conventions.md
```

Expected: approximately 140-150 lines.

- [ ] **Step 3: Commit**

```bash
git add skills/bigeye/references/conventions.md
git commit -m "feat: add shared conventions reference for all BigEye skills"
```

---

### Task 3: Hub Skill (`/bigeye`)

**Files:**
- Create: `skills/bigeye/SKILL.md`

- [ ] **Step 1: Create the hub skill**

Create `skills/bigeye/SKILL.md`:

```markdown
---
name: bigeye
description: Use when the user mentions BigEye, data quality issues, monitoring gaps, data freshness, monitor coverage, issue triage, root cause analysis, or when BigEye MCP tools are being used in conversation. Routes to the appropriate BigEye sub-skill.
user-invocable: true
---

# BigEye Data Observability Hub

Central entry point for all BigEye monitoring workflows. Routes to the right sub-skill based on user intent.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for shared formatting and severity rules.

## Available Skills

| Skill | Command | Purpose |
|-------|---------|---------|
| Triage | `/bigeye-triage` | What's on fire? Prioritized active issues |
| Root Cause Analysis | `/bigeye-rca` | Why is this broken? Lineage-traced diagnosis |
| Coverage | `/bigeye-coverage` | What's not monitored? Dimension/column gaps |
| Deploy | `/bigeye-deploy` | Set up monitors with sensible defaults |
| Incidents | `/bigeye-incidents` | Group related issues into incidents |

## Routing

Parse the user's input and invoke the matching sub-skill using the Skill tool:

| User intent | Invoke |
|-------------|--------|
| "what's broken?", "show active issues", "what's on fire", "triage", "status" | Skill: `bigeye-triage` |
| "why is issue X failing?", "what caused this?", "root cause", "trace", "debug" | Skill: `bigeye-rca` with issue reference as args |
| "what's not monitored?", "find gaps", "coverage", "missing monitors" | Skill: `bigeye-coverage` |
| "add monitors", "deploy", "set up monitoring", "create metric" | Skill: `bigeye-deploy` |
| "group issues", "create incident", "merge issues", "incident" | Skill: `bigeye-incidents` |

## Ambiguous Intent

If the user's intent doesn't clearly match one skill, present this menu:

```
What would you like to do?

1. **Triage** — See active issues prioritized by severity (`/bigeye-triage`)
2. **Root Cause Analysis** — Trace why an issue is happening (`/bigeye-rca`)
3. **Coverage** — Find monitoring gaps (`/bigeye-coverage`)
4. **Deploy Monitors** — Set up new monitors (`/bigeye-deploy`)
5. **Incidents** — Group related issues (`/bigeye-incidents`)
```

## With Arguments

If invoked as `/bigeye <text>`, pass `<text>` through the routing logic above. Examples:
- `/bigeye what's broken` → invoke `bigeye-triage`
- `/bigeye rca 10921` → invoke `bigeye-rca` with args `10921`
- `/bigeye coverage columns email` → invoke `bigeye-coverage` with args `columns email`
```

- [ ] **Step 2: Verify frontmatter is valid**

Read the file back and confirm the YAML frontmatter has `name`, `description`, and `user-invocable` fields.

- [ ] **Step 3: Commit**

```bash
git add skills/bigeye/SKILL.md
git commit -m "feat: add hub skill for BigEye routing and auto-trigger"
```

---

### Task 4: Triage Skill (`/bigeye-triage`)

**Files:**
- Create: `skills/bigeye-triage/SKILL.md`

- [ ] **Step 1: Create the triage skill**

Create `skills/bigeye-triage/SKILL.md`:

```markdown
---
name: bigeye-triage
description: Use when the user wants to see active BigEye issues, asks what's broken or on fire, or needs a prioritized view of data quality problems
user-invocable: true
---

# BigEye Triage

Answers "what's on fire?" — fetches all active issues and presents them prioritized by severity.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for severity classification rules and output formatting.

## Arguments

Parse `$ARGUMENTS` (space-separated):
- Empty or no args: show all open issues (NEW + ACKNOWLEDGED)
- `new`: only NEW status issues (unacknowledged)
- `24h`: issues opened in the last 24 hours only
- A number like `50`: override max_issues limit

## Procedure

### Step 1: Fetch Active Issues

Call `mcp__bigeye__list_issues` with:
- `statuses`: `["ISSUE_STATUS_NEW", "ISSUE_STATUS_ACKNOWLEDGED"]`
  - If argument is `new`, use only `["ISSUE_STATUS_NEW"]`
- `compact`: `false` (we need metric info for severity classification)
- `max_issues`: `50` (or user-specified override)

If no issues returned, report "No active issues — all clear." and stop.

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
```

- [ ] **Step 2: Verify the file**

Read the file back and confirm it has correct frontmatter and all 5 procedure steps.

- [ ] **Step 3: Commit**

```bash
git add skills/bigeye-triage/SKILL.md
git commit -m "feat: add triage skill for prioritized issue view"
```

---

### Task 5: Root Cause Analysis Skill (`/bigeye-rca`)

**Files:**
- Create: `skills/bigeye-rca/SKILL.md`

- [ ] **Step 1: Create the RCA skill**

Create `skills/bigeye-rca/SKILL.md`:

```markdown
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
```

- [ ] **Step 2: Verify the file**

Read the file back and confirm it has correct frontmatter and all 6 procedure steps.

- [ ] **Step 3: Commit**

```bash
git add skills/bigeye-rca/SKILL.md
git commit -m "feat: add root cause analysis skill with lineage tracing"
```

---

### Task 6: Coverage Analysis Skill (`/bigeye-coverage`)

**Files:**
- Create: `skills/bigeye-coverage/SKILL.md`

- [ ] **Step 1: Create the coverage skill**

Create `skills/bigeye-coverage/SKILL.md`:

```markdown
---
name: bigeye-coverage
description: Use when the user wants to find monitoring gaps, check which columns or dimensions lack monitors, or assess overall monitoring coverage on their table
user-invocable: true
---

# BigEye Coverage Analysis

Answers "what's not monitored?" — analyzes dimension coverage across columns and prioritizes gaps.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for output formatting and severity rules.

## Arguments

Parse `$ARGUMENTS`:
- Empty: full coverage report for the table
- `columns {col1},{col2}`: coverage for specific columns only
- `dimension {name}`: filter by a specific dimension (e.g., `validity`, `freshness`)

## Procedure

### Step 1: Get Table Dimension Coverage

Call `mcp__bigeye__get_table_dimension_coverage` with `table_name: "{table_name}"`.

If the table name is unknown, call `mcp__bigeye__list_data_sources` first to discover available tables, then ask the user which table to analyze.

This returns:
- Overall coverage score (percentage)
- Per-column coverage with gaps
- Table-level dimension coverage
- Suggested metrics for gaps

### Step 2: Get Dimension Taxonomy

Call `mcp__bigeye__list_dimensions` to get the full list of dimensions and their categories (PIPELINE_RELIABILITY vs DATA_QUALITY).

### Step 3: Get Column-Level Detail (if specific columns requested)

If the user specified columns via `columns {col1},{col2}`:
Call `mcp__bigeye__get_column_dimension_coverage` with:
- `table_name: "{table_name}"`
- `column_names: ["{col1}", "{col2}"]`

### Step 4: Prioritize Gaps

For gap prioritization, fetch past issues:
Call `mcp__bigeye__list_table_issues` with:
- `table_name: "{table_name}"`
- `statuses: ["ISSUE_STATUS_NEW", "ISSUE_STATUS_ACKNOWLEDGED", "ISSUE_STATUS_CLOSED"]`

Prioritize gaps:
- **HIGH**: Column had issues in the last 30 days AND has missing dimensions
- **MEDIUM**: Column has no recent issues but is missing critical dimensions (Freshness, Volume, Uniqueness, Completeness)
- **LOW**: Column is missing only non-critical dimensions (Distribution, Format)

If the `dimension` argument was provided, filter the gap list to only show gaps for that dimension.

### Step 5: Format Output

```
## Coverage Report — {schema}.{table_name}

### Overall Score: {percent}% ({covered} of {total} dimension-column pairs covered)

### Table-Level Coverage
| Dimension | Category | Status | Monitor |
|-----------|----------|--------|---------|
| Freshness | Pipeline Reliability | {Covered/GAP} | {metric name or "—"} |
| Volume | Pipeline Reliability | {Covered/GAP} | {metric name or "—"} |
| Schema Change | Pipeline Reliability | {Covered/GAP} | {metric name or "—"} |
| Validity | Data Quality | {Covered/GAP} | {metric name or "—"} |
| Completeness | Data Quality | {Covered/GAP} | {metric name or "—"} |
| Uniqueness | Data Quality | {Covered/GAP} | {metric name or "—"} |
| Distribution | Data Quality | {Covered/GAP} | {metric name or "—"} |

### Top Column Gaps (prioritized)
| Column | Missing Dimensions | Past Issues (30d) | Priority |
|--------|-------------------|-------------------|----------|
| {column} | {dim1}, {dim2} | {count} issues | HIGH |

{Show top 20 columns. If more gaps exist, note "... and N more columns with gaps."}

### Suggested Monitor Deployment
{count} monitors recommended to close high-priority gaps:
- {N} {Dimension} monitors ({column_list})
- {N} {Dimension} monitors ({column_list})
...

-> Run `/bigeye-deploy gaps` to deploy all suggested monitors
-> Run `/bigeye-deploy gaps --priority high` for high-priority only
```
```

- [ ] **Step 2: Verify the file**

Read the file back and confirm it has correct frontmatter and all 5 procedure steps.

- [ ] **Step 3: Commit**

```bash
git add skills/bigeye-coverage/SKILL.md
git commit -m "feat: add coverage analysis skill with gap prioritization"
```

---

### Task 7: Monitor Deployment Skill (`/bigeye-deploy`)

**Files:**
- Create: `skills/bigeye-deploy/SKILL.md`

- [ ] **Step 1: Create the deploy skill**

Create `skills/bigeye-deploy/SKILL.md`:

```markdown
---
name: bigeye-deploy
description: Use when the user wants to create monitors, deploy metrics, set up freshness checks, or close monitoring gaps identified by coverage analysis
user-invocable: true
---

# BigEye Monitor Deployment

Bulk monitor creation with sensible defaults and a mandatory confirmation gate.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for tag conventions, output formatting, and defaults.

<HARD-GATE>
NEVER create monitors without showing the deployment plan and receiving explicit user confirmation.
This is a write operation that creates real monitors in production BigEye.
</HARD-GATE>

## Arguments

Parse `$ARGUMENTS`:
- `gaps`: deploy all suggestions from the most recent coverage analysis
- `gaps --priority high`: only high-priority gaps
- `gaps --priority medium`: medium and high priority gaps
- `columns {col1},{col2}`: specific columns — auto-suggest metric types
- `freshness`: add a freshness monitor to the table
- `bulk {dimension}`: apply a dimension across all unmonitored columns

## Procedure

### Step 1: Build Deployment Plan

**For `gaps` argument:**
1. Call `mcp__bigeye__get_table_dimension_coverage` to get the current gap analysis
2. Extract suggested metrics from the coverage result
3. If `--priority high` is specified, filter to only HIGH priority gaps
4. If `--priority medium`, include MEDIUM and HIGH

**For `columns {col1},{col2}` argument:**
1. Call `mcp__bigeye__get_column_dimension_coverage` with the specified columns
2. For each gap, select the appropriate metric type based on dimension:
   - Completeness → PERCENT_NULL
   - Uniqueness → COUNT_DISTINCT
   - Validity → appropriate type based on column data type
   - Freshness → FRESHNESS (table-level only)
   - Volume → COUNT_ROWS (table-level only)

**For `freshness` argument:**
1. Build a single-row plan: table-level FRESHNESS metric

**For `bulk {dimension}` argument:**
1. Call `mcp__bigeye__get_table_dimension_coverage`
2. Find all columns missing coverage for that dimension
3. Build a plan with the appropriate metric type for each column

### Step 2: Present Deployment Plan

Show the plan in this exact format and WAIT for user confirmation:

```
## Deploy Plan — {count} monitors on {table_name}

| # | Column | Metric Type | Dimension | Lookback |
|---|--------|-------------|-----------|----------|
| 1 | {column or "—" for table-level} | {metric_type} | {dimension} | 7 days |
| 2 | ... | ... | ... | 7 days |

**Defaults applied:**
- Lookback: 7 days (DATA_TIME)
- No filters or group-bys

**Proceed? (y/n/edit)**
- `y` — create all monitors as shown
- `n` — cancel deployment
- `edit` — describe changes (e.g., "remove row 3", "change lookback to 14 days for row 1")
```

If the user says `edit`, apply their changes and re-present the plan. Repeat until they confirm with `y` or cancel with `n`.

### Step 3: Ensure Tracking Tag Exists

1. Call `mcp__bigeye__list_tags` with `search: "deployed-by-plugin"`
2. If no tag found, call `mcp__bigeye__create_tag` with `name: "deployed-by-plugin"`, `color_hex: "#6366F1"`
3. Store the `tag_id` for Step 5

### Step 4: Create Monitors

For each row in the confirmed plan, call `mcp__bigeye__create_metric` with:
- `table_name: "{table_name}"`
- `metric_type: "{metric_type}"`
- `column_name: "{column}"` (omit for table-level metrics like FRESHNESS, COUNT_ROWS)
- `lookback_type: "DATA_TIME"`
- `lookback_interval_type: "DAYS"`
- `lookback_interval_value: 7` (or user-specified)
- `schema_name: "{schema}"` (if known)

Track successes and failures separately.

### Step 5: Tag Created Monitors

For each successfully created monitor, call `mcp__bigeye__tag_entity` with:
- `tag_id: {tag_id from Step 3}`
- `entity_id: {metric_id from create_metric result}`
- `entity_type: "METRIC"`

### Step 6: Report Results

```
## Deployment Results

{success_count}/{total_count} monitors created successfully
{If any failures:}
Failed:
- {metric_type} on {column}: {error_message}

Created monitor IDs: {id_list}
All monitors tagged with `deployed-by-plugin` for tracking.

-> Run `/bigeye-triage` in ~1 hour to verify monitors are collecting data
```
```

- [ ] **Step 2: Verify the file**

Read the file back and confirm it has correct frontmatter, the HARD-GATE, and all 6 procedure steps.

- [ ] **Step 3: Commit**

```bash
git add skills/bigeye-deploy/SKILL.md
git commit -m "feat: add monitor deployment skill with confirmation gate"
```

---

### Task 8: Incident Management Skill (`/bigeye-incidents`)

**Files:**
- Create: `skills/bigeye-incidents/SKILL.md`

- [ ] **Step 1: Create the incidents skill**

Create `skills/bigeye-incidents/SKILL.md`:

```markdown
---
name: bigeye-incidents
description: Use when the user wants to group related BigEye issues into incidents, merge issues, manage existing incidents, or auto-detect issue clusters
user-invocable: true
---

# BigEye Incident Management

Group related issues into incidents, manage existing incidents, and auto-detect issue clusters.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for status mapping and output formatting.

<HARD-GATE>
NEVER create or modify incidents without showing the plan and receiving explicit user confirmation.
Incidents affect issue visibility and tracking in the BigEye UI for the entire team.
</HARD-GATE>

## Arguments

Parse `$ARGUMENTS`:
- `{id1} {id2} {id3}`: merge these specific issues (display names) into a new incident
- `auto`: auto-detect clusters from open issues and suggest groupings
- `add {id} to {incident_id}`: add an issue to an existing incident
- `close {id} --label {label}`: close an incident with a closing label

## Procedure

### Mode: Merge Specific Issues (`{id1} {id2} ...`)

**Step 1: Resolve issue IDs**

For each display name provided, call `mcp__bigeye__search_issues` with `name_query: "{display_name}"`.
Collect internal IDs. If any name doesn't resolve, report it and ask the user to correct.

At least 2 issue IDs are required for a new incident.

**Step 2: Validate relationship**

For the first issue, call `mcp__bigeye__list_related_issues` with `starting_issue_id: {first_id}`.
Check if the other issues appear in the related list.

If issues are NOT related via lineage, warn the user:
"These issues don't appear to be related through data lineage. They may still belong to the same incident if they share a common cause. Proceed anyway? (y/n)"

**Step 3: Generate incident name**

Auto-generate a descriptive name from the issues:
- Find the root cause issue (the one with `isRootCause: true` in related issues, or the earliest opened)
- Format: "{dimension} issue affecting {table_name}" or "{root_cause_dimension} cascade from {source_table}"

**Step 4: Present plan and confirm**

```
## Create Incident — "{generated_name}"

Issues to merge:
| Issue | Dimension | Table | Column | Status | Root Cause? |
|-------|-----------|-------|--------|--------|-------------|
| {display_name} | {dim} | {table} | {col} | {status} | {yes/no} |

Proceed? (y/n/edit name)
```

Wait for confirmation.

**Step 5: Create incident**

Call `mcp__bigeye__create_incident` with:
- `issue_ids: [{internal_id_1}, {internal_id_2}, ...]`
- `incident_name: "{generated_name}"`

**Step 6: Report result**

```
## Incident Created — "{name}"

Issues merged:
- #{display_name_1} (root cause) — {description}
- #{display_name_2} — {description}

Root cause: #{root_cause_display_name} (flagged by lineage)
Downstream impact: {related_count} issues

-> Deep dive: `/bigeye-rca {root_cause_display_name}`
-> Acknowledge all issues in this incident
```

### Mode: Auto-Detect (`auto`)

**Step 1: Fetch open issues**

Call `mcp__bigeye__list_issues` with:
- `statuses: ["ISSUE_STATUS_NEW", "ISSUE_STATUS_ACKNOWLEDGED"]`
- `compact: false`
- `max_issues: 50`

**Step 2: Build relationship graph**

For each issue, call `mcp__bigeye__list_related_issues` with `starting_issue_id: {id}`.

Build clusters: group issues that share any related issue. Two issues are in the same cluster if they share at least one related issue (transitive closure).

**Step 3: Present suggested clusters**

```
## Auto-Detected Issue Clusters

### Cluster 1: "{auto_name}" ({count} issues)
| Issue | Dimension | Table | Root Cause? |
|-------|-----------|-------|-------------|
| ... | ... | ... | ... |

### Cluster 2: "{auto_name}" ({count} issues)
| Issue | Dimension | Table | Root Cause? |
|-------|-----------|-------|-------------|

{count_unclustered} issues have no detected relationships (not shown).

Create incidents for these clusters? (all/1,2/none)
```

- `all`: create incidents for all clusters
- `1,2`: create incidents for specified cluster numbers
- `none`: cancel

**Step 4:** For each confirmed cluster, follow Steps 3-6 from the "Merge Specific Issues" mode above.

### Mode: Add to Existing (`add {id} to {incident_id}`)

1. Resolve both display names to internal IDs via `mcp__bigeye__search_issues`
2. Call `mcp__bigeye__create_incident` with `issue_ids: [{issue_id}]`, `existing_incident_id: {incident_internal_id}`
3. Report result

### Mode: Close (`close {id} --label {label}`)

1. Resolve display name to internal ID
2. Map label shorthand to API value:
   - `true-negative` → `METRIC_RUN_LABEL_TRUE_NEGATIVE`
   - `false-positive` → `METRIC_RUN_LABEL_FALSE_POSITIVE`
3. Call `mcp__bigeye__update_issue` with:
   - `issue_id: {internal_id}`
   - `new_status: "ISSUE_STATUS_CLOSED"`
   - `closing_label: "{mapped_label}"`
4. Report result
```

- [ ] **Step 2: Verify the file**

Read the file back and confirm it has correct frontmatter, the HARD-GATE, and all 4 modes with their procedures.

- [ ] **Step 3: Commit**

```bash
git add skills/bigeye-incidents/SKILL.md
git commit -m "feat: add incident management skill with auto-detect clustering"
```

---

### Task 9: Morning Report Agent

**Files:**
- Create: `agents/bigeye-morning-report.md`

- [ ] **Step 1: Create the morning report agent**

Create `agents/bigeye-morning-report.md`:

```markdown
---
name: bigeye-morning-report
description: |
  Scheduled daily agent that produces a BigEye data quality summary and sends a Slack notification. Use with: /schedule create "0 8 * * *" /bigeye-morning-report
model: inherit
---

You are the BigEye Morning Report agent. Your job is to produce a daily data quality summary for the team and send a short notification to Slack.

**IMPORTANT: You are read-only. You NEVER modify issues, create monitors, or take any write actions. You only observe and report.**

Before starting, read `skills/bigeye/references/conventions.md` for severity classification, output formatting, and Slack templates.

## Workflow

Execute these steps in order:

### 1. Triage — Current Issue State

Call `mcp__bigeye__list_issues` with:
- `statuses: ["ISSUE_STATUS_NEW", "ISSUE_STATUS_ACKNOWLEDGED"]`
- `compact: false`
- `max_issues: 50`

Classify each issue by severity using the rules in conventions.md.

Count:
- Total open issues
- Critical / Warning / Low breakdown
- How many are NEW (unacknowledged)

### 2. Cluster Detection

For each Critical and Warning issue, call `mcp__bigeye__list_related_issues` with `starting_issue_id`.

Count how many distinct clusters exist (groups of 2+ related issues).

### 3. Coverage Check

Call `mcp__bigeye__get_table_dimension_coverage` with the monitored table.

Record the overall coverage percentage.

### 4. Produce Terminal Report

Output this format:

```
## Morning Report — {date} {time}

### Current State
- {total} open issues ({critical} critical, {warning} warning, {low} low)
- {new_count} unacknowledged (NEW)
- {cluster_count} issue clusters detected
- Coverage: {percent}%

### Critical Issues
| Issue | Dimension | Column | Since | Related |
|-------|-----------|--------|-------|---------|
{list all critical issues}

### Action Items
1. {If clusters: "Group related issues: `/bigeye-incidents auto`"}
2. {If critical: "Investigate top critical: `/bigeye-rca {top_issue}`"}
3. {If unacknowledged > 5: "Triage unacknowledged issues: `/bigeye-triage new`"}
4. {If coverage < 80%: "Review monitoring gaps: `/bigeye-coverage`"}
```

### 5. Send Slack Notification

**Only send if there are new Critical issues since last report.**

If there are Critical issues, authenticate with Slack MCP if needed (use `mcp__claude_ai_Slack__authenticate` / `mcp__claude_ai_Slack__complete_authentication`), then send a message to the configured channel.

Use the Slack morning report template from conventions.md:

```
BigEye Morning Report — {date}

{critical_count} critical | {warning_count} warning | {low_count} low

Top issues:
- #{issue_1}: {dimension} on {column} ({time_since})
- #{issue_2}: {dimension} on {column} ({time_since})
- #{issue_3}: {dimension} on {column} ({time_since})

Coverage: {percent}%
Run /bigeye-triage in Claude Code for details
```

If `critical_count > 0`, prepend with `@data-oncall` mention per conventions.md.

If there are zero Critical issues and no new Warning issues, skip the Slack notification entirely — don't create noise on quiet days.
```

- [ ] **Step 2: Verify the file**

Read the file back and confirm it has correct frontmatter with `model: inherit` and all 5 workflow steps.

- [ ] **Step 3: Commit**

```bash
git add agents/bigeye-morning-report.md
git commit -m "feat: add morning report agent with Slack integration"
```

---

### Task 10: Hooks Configuration

**Files:**
- Create: `hooks/hooks.json`

- [ ] **Step 1: Create the hooks file**

Create `hooks/hooks.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|clear|compact",
        "hooks": [
          {
            "type": "message",
            "message": "BigEye Data Observability plugin is active. Available commands: /bigeye, /bigeye-triage, /bigeye-rca, /bigeye-coverage, /bigeye-deploy, /bigeye-incidents. Say /bigeye to get started."
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Verify valid JSON**

```bash
python3 -c "import json; json.load(open('hooks/hooks.json')); print('Valid JSON')"
```

Expected: `Valid JSON`

- [ ] **Step 3: Commit**

```bash
git add hooks/hooks.json
git commit -m "feat: add session start hook for BigEye plugin"
```

---

### Task 11: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create the README**

Create `README.md`:

```markdown
# BigEye Data Observability Plugin

A Claude Code plugin for managing BigEye monitoring at scale. Simplifies triage, root cause analysis, coverage gaps, monitor deployment, and incident management — all through natural language or slash commands.

## Requirements

- Claude Code with plugin support
- BigEye MCP server configured and authenticated
- Slack MCP server (optional, for morning report notifications)

## Installation

Install directly from the project directory:

```bash
claude plugins install /path/to/bigeye-plugin
```

Or add to your Claude Code settings as a local plugin.

## Commands

| Command | Description |
|---------|-------------|
| `/bigeye` | Smart router — describe what you need in natural language |
| `/bigeye-triage` | Prioritized view of active issues |
| `/bigeye-rca [issue#]` | Root cause analysis with lineage tracing |
| `/bigeye-coverage` | Find monitoring gaps across dimensions |
| `/bigeye-deploy [target]` | Deploy monitors with confirmation |
| `/bigeye-incidents [ids/auto]` | Group related issues into incidents |

## Scheduled Agent

Set up the daily morning report:

```bash
/schedule create "0 8 * * *" /bigeye-morning-report
```

This runs triage every morning at 8am, produces a summary, and sends a Slack notification for critical issues.

## Configuration

Edit `skills/bigeye/references/conventions.md` to customize:
- Slack channel and mention groups
- Severity classification thresholds
- Output formatting preferences
- Default monitor settings

## Skill Chaining

Skills suggest the logical next step:

```
/bigeye-triage → /bigeye-rca 10921 → /bigeye-incidents 10919 10920 10921
/bigeye-coverage → /bigeye-deploy gaps --priority high
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with installation and usage guide"
```

---

### Task 12: Verify Complete Plugin

- [ ] **Step 1: Verify all files exist**

```bash
find . -type f -not -path './.venv/*' -not -path './.idea/*' -not -path './docs/*' | sort
```

Expected files:
```
./.claude-plugin/plugin.json
./README.md
./agents/bigeye-morning-report.md
./hooks/hooks.json
./pyproject.toml
./skills/bigeye/SKILL.md
./skills/bigeye/references/conventions.md
./skills/bigeye-coverage/SKILL.md
./skills/bigeye-deploy/SKILL.md
./skills/bigeye-incidents/SKILL.md
./skills/bigeye-rca/SKILL.md
./skills/bigeye-triage/SKILL.md
```

- [ ] **Step 2: Verify all SKILL.md files have valid frontmatter**

```bash
for f in skills/*/SKILL.md; do echo "=== $f ==="; head -4 "$f"; echo; done
```

Each should show `---`, `name:`, `description:`, `---`.

- [ ] **Step 3: Verify plugin.json is valid**

```bash
python3 -c "import json; d=json.load(open('.claude-plugin/plugin.json')); print(f'Plugin: {d[\"name\"]} v{d[\"version\"]}')"
```

Expected: `Plugin: bigeye v0.1.0`

- [ ] **Step 4: Verify hooks.json is valid**

```bash
python3 -c "import json; d=json.load(open('hooks/hooks.json')); print(f'Hooks: {list(d[\"hooks\"].keys())}')"
```

Expected: `Hooks: ['SessionStart']`

- [ ] **Step 5: Final commit (if any unstaged changes)**

```bash
git status
```

If clean, done. If any unstaged files, add and commit with message "chore: final cleanup".
