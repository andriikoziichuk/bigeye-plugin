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
