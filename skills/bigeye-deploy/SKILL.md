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
