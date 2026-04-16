# BigEye Data Observability Plugin — Design Spec

## Overview

A Claude Code plugin that simplifies BigEye monitoring at scale for a team managing one massive table with many columns and monitors. The plugin provides slash commands, auto-triggering skills, and a scheduled agent — all backed by the BigEye MCP server.

**Target users:** Data team members with varying BigEye expertise; polished enough to distribute externally.

**Core principle:** Surface what matters, trace why it's broken, close the gaps, and keep the team informed — with confirmation gates on all write operations.

---

## Plugin Structure

```
bigeye-plugin/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── bigeye/
│   │   ├── SKILL.md                     # Hub skill — routes & auto-triggers
│   │   └── references/
│   │       └── conventions.md           # Shared formatting, severity logic, Slack templates
│   ├── bigeye-triage/
│   │   └── SKILL.md                     # /bigeye-triage
│   ├── bigeye-rca/
│   │   └── SKILL.md                     # /bigeye-rca
│   ├── bigeye-coverage/
│   │   └── SKILL.md                     # /bigeye-coverage
│   ├── bigeye-deploy/
│   │   └── SKILL.md                     # /bigeye-deploy
│   └── bigeye-incidents/
│       └── SKILL.md                     # /bigeye-incidents
├── agents/
│   └── bigeye-morning-report.md         # Scheduled daily triage agent
├── hooks/
│   └── hooks.json                       # Auto-trigger on BigEye keywords
├── README.md
└── LICENSE
```

### plugin.json

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

---

## Component Specifications

### 1. Hub Skill (`/bigeye`)

**File:** `skills/bigeye/SKILL.md`

**Purpose:** Central entry point that routes natural language to the right sub-skill. Also auto-triggers when BigEye-related keywords appear in conversation.

**Routing logic:**

| User intent | Routes to |
|-------------|-----------|
| "what's broken?", "show active issues", "what's on fire" | `/bigeye-triage` |
| "why is issue X failing?", "what caused this?" | `/bigeye-rca` |
| "what's not monitored?", "find coverage gaps" | `/bigeye-coverage` |
| "add monitors for column X", "set up freshness checks" | `/bigeye-deploy` |
| "group these issues", "create incident from X, Y" | `/bigeye-incidents` |

When intent is ambiguous, presents a short menu rather than guessing.

**Auto-trigger description:** `Use when the user mentions BigEye, data quality issues, monitoring gaps, data freshness, or when BigEye MCP tools are being used in conversation`

---

### 2. Triage Skill (`/bigeye-triage`)

**File:** `skills/bigeye-triage/SKILL.md`

**Purpose:** Answers "what's on fire?" — prioritized view of all active issues.

**MCP tools used:**
- `list_issues` — fetch open issues (statuses: NEW, ACKNOWLEDGED)
- `list_related_issues` — detect issue clusters per issue
- `get_issue` — full details when needed

**Severity classification:**
- **Critical:** Freshness/Volume issues (pipeline broken), or any issue older than 4 hours still in NEW status
- **Warning:** Data quality issues (nulls, validity, uniqueness) with high impact
- **Low:** Recently opened, low-impact dimensions, or already ACKNOWLEDGED

**Output format:**
```
## BigEye Triage — YYYY-MM-DD

### Critical (N issues)
| # | Issue | Dimension | Column | Since | Related |
|---|-------|-----------|--------|-------|---------|

### Warning (N issues)
| # | Issue | Dimension | Column | Since | Related |
|---|-------|-----------|--------|-------|---------|

### Summary
- N critical, N warning, N low
- N issue clusters detected
- Suggested next: `/bigeye-rca <top-issue>` for top critical
```

**Arguments:**
- `/bigeye-triage` — all open issues
- `/bigeye-triage new` — only NEW status (unacknowledged)
- `/bigeye-triage 24h` — issues opened in last 24 hours

---

### 3. Root Cause Analysis Skill (`/bigeye-rca`)

**File:** `skills/bigeye-rca/SKILL.md`

**Purpose:** Answers "why is this broken?" — traces an issue through lineage to find origin.

**MCP tools used:**
- `search_issues` — resolve display name to internal ID
- `get_issue` — full issue details and event history
- `get_issue_lineage_trace` — end-to-end upstream/downstream analysis
- `get_resolution_steps` — recommended fixes
- `list_related_issues` — sibling issues with shared root cause

**Output format:**
```
## Root Cause Analysis — Issue #XXXXX

### Issue
<metric type> failed on <table>
<timing details>

### Lineage Trace
<visual trace showing upstream path>
↑ ROOT CAUSE HERE (if found)

### Related Issues (same root cause)
- <list of sibling issues>

### Resolution Steps
1. <step-by-step from get_resolution_steps>

### Suggested Actions
- <incident creation if multiple related>
- <acknowledge option>
```

**Arguments:**
- `/bigeye-rca 10921` — by issue display name
- `/bigeye-rca` (no args) — runs a lightweight triage (`list_issues`, limit 5, sorted by severity) and picks the top critical issue

**Key behaviors:**
- Highlights root cause prominently rather than burying in graph
- Proactively suggests incident creation when multiple issues share root cause
- Always ends with actionable next steps

---

### 4. Coverage Analysis Skill (`/bigeye-coverage`)

**File:** `skills/bigeye-coverage/SKILL.md`

**Purpose:** Answers "what's not monitored?" — finds dimension/column gaps and suggests monitors.

**MCP tools used:**
- `get_table_dimension_coverage` — aggregate coverage, gaps, suggestions
- `list_dimensions` — full dimension taxonomy
- `get_column_dimension_coverage` — per-column deep dive
- `list_table_issues` — fetch past issues per table for gap prioritization

**Output format:**
```
## Coverage Report — SCHEMA.TABLE

### Overall Score: XX% (N of M dimension-column pairs covered)

### Table-Level Coverage
| Dimension | Status | Monitor |
|-----------|--------|---------|

### Top Column Gaps (prioritized)
| Column | Missing Dimensions | Past Issues | Priority |
|--------|-------------------|-------------|----------|

### Suggested Monitor Deployment
<summary of suggested monitors>
→ Run `/bigeye-deploy gaps` to deploy
```

**Gap prioritization logic:**
- Columns with past issues in last 30 days ranked HIGH
- Columns with no issues but missing critical dimensions (freshness, volume, uniqueness) ranked MEDIUM
- All other gaps ranked LOW

**Arguments:**
- `/bigeye-coverage` — full coverage report
- `/bigeye-coverage columns email,user_id` — specific columns
- `/bigeye-coverage dimension validity` — filter by dimension

---

### 5. Monitor Deployment Skill (`/bigeye-deploy`)

**File:** `skills/bigeye-deploy/SKILL.md`

**Purpose:** Bulk monitor creation with sensible defaults and mandatory confirmation gate.

**MCP tools used:**
- `create_metric` — create each monitor
- `get_table_dimension_coverage` — when deploying from gap analysis
- `create_tag` / `tag_entity` — tag newly created monitors with `deployed-by-plugin`
- `list_tags` — check if tracking tag exists

**Deployment flow:**
1. Build deployment plan (from gaps, specific columns, or dimension)
2. Present plan table for review — NEVER create without confirmation
3. On confirmation, create metrics sequentially
4. Report results with success/failure per monitor
5. Tag all created monitors for tracking

**Deployment plan format:**
```
## Deploy Plan — N monitors

| # | Column | Metric Type | Dimension | Lookback |
|---|--------|-------------|-----------|----------|

Proceed? (y/n/edit)
```

**Defaults:**
- Lookback: 7 days
- Lookback type: DATA_TIME
- No filters or group-bys (user can edit plan to add)

**Arguments:**
- `/bigeye-deploy gaps` — deploy all suggestions from last coverage
- `/bigeye-deploy gaps --priority high` — high-priority only
- `/bigeye-deploy columns email,user_id` — specific columns, auto-suggest metrics
- `/bigeye-deploy freshness` — add freshness monitor to table
- `/bigeye-deploy bulk <dimension>` — apply dimension across unmonitored columns

---

### 6. Incident Management Skill (`/bigeye-incidents`)

**File:** `skills/bigeye-incidents/SKILL.md`

**Purpose:** Group related issues into incidents, manage existing incidents.

**MCP tools used:**
- `search_issues` — resolve display names to internal IDs
- `list_related_issues` — validate relationship and build cluster graph
- `create_incident` — create incident from issue group
- `delete_incident_members` — remove issues from incident
- `update_issue` — acknowledge/close issues within incident
- `list_issues` — for auto-detect mode

**Auto-detect mode (`/bigeye-incidents auto`):**
1. Fetch all open issues
2. For each, call `list_related_issues` to build relationship graph
3. Group into clusters where issues share upstream root causes
4. Present suggested incidents for confirmation

**Output format:**
```
## Incident Created — "<auto-generated name>"

Issues merged:
- #XXXXX (root cause) — <description>
- #XXXXX — <description>

Root cause: #XXXXX (flagged by lineage)
Downstream impact: N issues, N tables
```

**Arguments:**
- `/bigeye-incidents 10919 10920 10921` — merge specific issues
- `/bigeye-incidents auto` — auto-detect clusters
- `/bigeye-incidents add 10923 to 10919` — add to existing incident
- `/bigeye-incidents close 10919 --label true-negative` — close with label

**Key behaviors:**
- Always confirms before creating/modifying
- Auto-names incidents based on root cause and affected table
- Suggests priority based on highest-severity issue in group

---

### 7. Morning Report Agent

**File:** `agents/bigeye-morning-report.md`

**Purpose:** Scheduled daily agent that composes sub-skills into a summary and pushes to Slack.

**Scheduled via:** `/schedule create "0 8 * * *" /bigeye-morning-report`

**Agent workflow:**
1. Run triage (new issues since last check)
2. Run coverage check (detect new gaps from schema changes)
3. Auto-detect incident clusters
4. Produce terminal summary + Slack notification

**Terminal output (detailed):**
```
## Morning Report — YYYY-MM-DD HH:MM

### Overnight Activity
- N new issues opened
- N issues auto-resolved
- N incidents created

### Current State
- N open issues (N critical, N warning)
- N incident clusters detected
- Coverage: XX%

### Action Items
1. <prioritized actions with skill commands>

### Trend (7-day)
<daily issue count trend>
```

**Slack notification (short):**
- Posts to configured channel via Slack MCP
- Includes: critical count, top issue summary, coverage score
- Only posts if there are new issues (no noise on quiet days)
- Mentions configured group (e.g., `@data-oncall`) for critical issues

**Key behaviors:**
- Read-only — never modifies issues or creates monitors automatically
- Skips Slack notification if nothing new since last report
- Configurable via conventions.md (channel, severity threshold, mention groups)

---

### 8. Shared Conventions

**File:** `skills/bigeye/references/conventions.md`

**Contents:**
- **Output formatting:** Severity indicators, table layouts, status display mapping
- **Status mapping:** `ISSUE_STATUS_NEW` → "New", `ISSUE_STATUS_ACKNOWLEDGED` → "Ack'd", etc.
- **Severity classification:** Rules for Critical/Warning/Low based on dimension, age, metric type
- **MCP tool patterns:** Table name resolution, pagination handling, error recovery
- **Slack templates:** Notification format, channel config, mention groups
- **Tag conventions:** `deployed-by-plugin` tag for tracking plugin-created monitors

---

### 9. Hooks

**File:** `hooks/hooks.json`

**Hook triggers:**
- **SessionStart:** Lightweight reminder that BigEye skills are available
- **PreToolCall (BigEye MCP tools):** Injects conventions reference for consistent formatting when BigEye tools are used outside explicit skill invocation

---

## Skill Chaining

Skills are designed to chain naturally:

```
/bigeye-triage
  → "3 critical issues, top is #10921"
    → /bigeye-rca 10921
      → "Root cause: #10919, 4 related issues"
        → /bigeye-incidents 10919 10920 10921 10922
          → Incident created

/bigeye-coverage
  → "67% covered, 12 high-priority gaps"
    → /bigeye-deploy gaps --priority high
      → Deployment plan, confirm, done
```

Each skill suggests the logical next skill in its output.

---

## Dependencies

**Required MCP servers:**
- `bigeye` — all BigEye operations (already configured)
- `claude_ai_Slack` — Slack notifications for morning report

**No Python/Node dependencies.** The plugin is pure markdown (skills + agents + hooks). All logic is expressed as instructions to Claude, executed via MCP tool calls.

---

## Out of Scope (for v0.1.0)

- Multi-table support (current focus: one massive table)
- Custom metric types / SQL-based monitors
- Historical trend analysis beyond 7-day window in morning report
- Integration with other notification channels (PagerDuty, email)
- User permission management within the plugin
