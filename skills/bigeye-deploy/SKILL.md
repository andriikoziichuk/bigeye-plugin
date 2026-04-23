---
name: bigeye-deploy
description: Use when the user wants to create monitors, deploy metrics, set up freshness checks, or close monitoring gaps identified by coverage analysis
user-invocable: true
---

# BigEye Monitor Deployment

Bulk monitor creation with sensible defaults and a mandatory confirmation gate.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for tag conventions, output formatting, and defaults, and `skills/bigeye/references/scope.md` for how to load and apply the active scope profile, and skills/bigeye/references/cli.md for CLI invocation rules and MCP-availability detection.

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
- `--metric-type <TYPE>`: required for `columns <list>` when MCP is unavailable. Applies the same metric type to all named columns. Valid types: `PERCENT_NULL`, `COUNT_DISTINCT`, `COUNT_ROWS`, `FRESHNESS`, etc. (see Bigeye docs).

## Procedure

### Step 0: Load Scope

Follow `skills/bigeye/references/scope.md` (Steps A–E) to load the active profile. Parse `--profile <name>`, `--no-scope`, and `--workspace <id>` from `$ARGUMENTS` before parsing the skill's own arguments. Then follow cli.md Step B to detect MCP availability (sets MCP_AVAILABLE).

For deploy:
- If the user named a specific target (`columns {cols}`, `freshness`, `bulk {dim}` against a named table), the scope's table filter does NOT restrict the target — the user's explicit target wins.
- If the user said `gaps`, deploy only to in-scope tables (iterate over each table from the working profile).

### Step 1: Build Deployment Plan

**For `gaps` / `bulk <dimension>` arguments** (bigconfig path):

1. If `MCP_AVAILABLE=false`:
   Print the `cli.md` Step F warning with `{feature_name}=coverage-driven deploy planning`. Stop — gaps/bulk hard-fail without coverage scoring.
2. Call `mcp__bigeye__get_table_dimension_coverage` per in-scope table to enumerate gaps.
3. Filter by `--priority high` (HIGH only) or `--priority medium` (HIGH + MEDIUM) if given.
4. For `bulk <dimension>`, filter the gap list to only that dimension.
5. Build a bigconfig YAML at `$TMPDIR/bigconfig.yaml` describing the desired metrics. Template (fill placeholders):
   ```yaml
   type: BIGCONFIG_FILE
   tag_deployments:
     - collection:
         name: plugin-deployed
       deployments:
         - fq_table_name: <data_source>.<schema>.<table>
           columns:
             - column_name: <column>
               metrics:
                 - saved_metric_id: <auto-named-id>
                   metric_type:
                     predefined_metric:
                       metric_name: <METRIC_TYPE>
                   lookback:
                     lookback_window: { interval_type: DAYS, interval_value: 7 }
                     lookback_type: DATA_TIME
   ```
   (If the exact Bigconfig schema differs when implementing, verify against `bigeye bigconfig export -op /tmp/sample` on a real workspace and correct the template.)

**For `columns <list>` argument** (imperative path):

1. If `MCP_AVAILABLE=true` and `--metric-type` was not passed:
   Call `mcp__bigeye__get_column_dimension_coverage` with `column_names` to infer a metric type per column per dimension.
2. If `MCP_AVAILABLE=false` and `--metric-type` was not passed:
   Print the `cli.md` Step F warning with `{feature_name}=per-column dimension inference` and `{CLI-only workaround}=Re-run with --metric-type <TYPE> to apply a single type to all columns`. Stop.
3. If `--metric-type` was passed: skip inference, use that type for every column.
4. Build one `SimpleUpsertMetricRequest` YAML file per column at `$TMPDIR/<column>.yaml`.

**For `freshness` argument** (imperative path, no MCP):

Build one `SimpleUpsertMetricRequest` YAML at `$TMPDIR/freshness.yaml` targeting a table-level `FRESHNESS` metric.

Template for `SimpleUpsertMetricRequest` (verify exact shape when implementing):
```yaml
schema_name: <schema>
table_name: <table>
column_name: <column or empty for table-level>
metric_type: <METRIC_TYPE>
lookback:
  lookback_window: { interval_type: DAYS, interval_value: 7 }
  lookback_type: DATA_TIME
```

### Step 2: Present Deployment Plan

Show the plan in this exact format and WAIT for user confirmation:

```
Scope: {per scope.md Step G}

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

Additionally show the exact CLI invocation that will run:
- For bigconfig path: `bigeye -w <profile> bigconfig plan -ip $TMPDIR -op $TMPDIR/plan/` (then `apply -auto_approve` on confirm).
- For imperative path: `bigeye -w <profile> metric upsert -f <file> -t SIMPLE` per file.

### Step 3: Ensure Tracking Tag Exists

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=monitor tagging` and `{CLI-only workaround}=Monitors will be created but not tagged — `deployed-by-plugin` tracking unavailable without MCP`. Set `SKIP_TAGGING=true`. Skip to Step 4.

If `MCP_AVAILABLE=true`:
  1. Call `mcp__bigeye__list_tags` with `search: "deployed-by-plugin"`
  2. If no tag found, call `mcp__bigeye__create_tag` with `name: "deployed-by-plugin"`, `color_hex: "#6366F1"`
  3. Store the `tag_id` for Step 5

### Step 4: Create Monitors

**Bigconfig path** (for `gaps` / `bulk`):

1. Run plan:
   ```bash
   bigeye -w <profile> bigconfig plan -ip "$TMPDIR" -op "$TMPDIR/plan"
   ```
2. Read the plan report; summarize to the user: *"Plan: N monitors to create, M to update, 0 errors."*
3. Ask re-confirmation: *"Apply now? (y/n)"*. On `n`, stop.
4. Run apply:
   ```bash
   bigeye -w <profile> bigconfig apply -ip "$TMPDIR" -auto_approve
   ```
5. Read the apply report. Extract created metric IDs (for tagging in Step 5).

**Imperative path** (for `freshness` / `columns`):

For each YAML file in `$TMPDIR`:
```bash
bigeye -w <profile> metric upsert -f <file_path> -t SIMPLE
```
Track successes and failures. Parse each command's output for the created metric ID.

### Step 5: Tag Created Monitors

If `SKIP_TAGGING=true` (from Step 3):
  Skip this step entirely.

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

If `SKIP_TAGGING=true`, append to the output:
`Note: monitors were NOT tagged (MCP unavailable). To backfill tags later, run `/bigeye-config verify` and then deploy again once MCP is configured.`
