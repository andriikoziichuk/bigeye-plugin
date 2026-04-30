---
name: bigeye-deploy
description: Use when the user wants to create monitors, deploy metrics, set up freshness checks, or close monitoring gaps identified by coverage analysis
user-invocable: true
---

# BigEye Monitor Deployment

What it does: bulk monitor creation with sensible defaults and a mandatory confirmation gate. Two paths: bigconfig (gaps/bulk) and imperative (freshness/columns).

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`.

<HARD-GATE>
NEVER create monitors without showing the deployment plan and receiving explicit user confirmation.
This is a write operation that creates real monitors in production BigEye.
</HARD-GATE>

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `gaps` | Deploy all suggestions from the most recent coverage analysis | `/bigeye-deploy gaps` |
| `gaps --priority high` | High-priority gaps only | `/bigeye-deploy gaps --priority high` |
| `gaps --priority medium` | Medium + high priority gaps | `/bigeye-deploy gaps --priority medium` |
| `columns <c1>,<c2>` | Deploy on specific columns; auto-suggest types | `/bigeye-deploy columns email` |
| `freshness` | Add a freshness monitor to the table | `/bigeye-deploy freshness` |
| `bulk <dimension>` | Apply a dimension across all unmonitored columns | `/bigeye-deploy bulk validity` |
| `--metric-type <TYPE>` | Required for `columns <list>` when MCP off; applies same type to all named columns | `/bigeye-deploy columns email --metric-type VALID_REGEX` |

Defaults applied (override via `/bigeye-config settings edit deploy.<key> <value>`):
- Lookback: `settings.json.deploy.default_lookback_days` (default 7).
- Tracking tag: `settings.json.deploy.tag` (default `deployed-by-plugin`).

Global flags — see `output.md`.

## Procedure

1. Follow `preamble.md` Steps 1–7. Read `settings.json.deploy.default_lookback_days` and `deploy.tag`.

2. Build the deployment plan.

   **For `gaps` / `bulk <dimension>`** (bigconfig path):
   - `MCP_AVAILABLE=false`: hard-fail per Step 7.B with `feature_name=coverage-driven deploy planning`.
   - `MCP_AVAILABLE=true`: per in-scope table, call `mcp__bigeye__get_table_dimension_coverage`. Filter by `--priority high|medium`. For `bulk <dimension>`, restrict to that dimension.
   - Build a bigconfig YAML at `$TMPDIR/bigconfig.yaml`:
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
                       lookback_window: { interval_type: DAYS, interval_value: <default_lookback_days> }
                       lookback_type: DATA_TIME
     ```

   **For `columns <list>`** (imperative path):
   - `MCP_AVAILABLE=true` and no `--metric-type`: `mcp__bigeye__get_column_dimension_coverage` to infer per-column types.
   - `MCP_AVAILABLE=false` and no `--metric-type`: hard-fail per Step 7.B with `feature_name=per-column dimension inference` and Fix `Re-run with --metric-type <TYPE>`.
   - `--metric-type` given: skip inference, use that type for every column.
   - Build one `SimpleUpsertMetricRequest` YAML per column at `$TMPDIR/<column>.yaml`:
     ```yaml
     schema_name: <schema>
     table_name: <table>
     column_name: <column>
     metric_type: <METRIC_TYPE>
     lookback:
       lookback_window: { interval_type: DAYS, interval_value: <default_lookback_days> }
       lookback_type: DATA_TIME
     ```

   **For `freshness`** (imperative, no MCP needed): same template, table-level (no `column_name`), metric_type `FRESHNESS`.

3. Print numbered progress per `output.md` §Progress indicators (`[1/4] Building plan ...`).

4. Present the plan and WAIT for confirmation:
   ```
   {scope pill}
   ## Deploy Plan — {count} monitors on {table_name}

   | # | Column | Metric Type | Dimension | Lookback |
   |---|---|---|---|---|
   | 1 | {col or —} | {metric_type} | {dimension} | {default_lookback_days} days |
   | 2 | ... | ... | ... | ... |

   Defaults applied:
   - Lookback: {default_lookback_days} days (DATA_TIME)
   - Tracking tag: {deploy.tag}

   Proceed? (y/n/edit)
   - y    — create all monitors as shown
   - n    — cancel deployment
   - edit — describe changes (e.g., "remove row 3", "change lookback to 14 days for row 1")
   ```
   Show the exact CLI invocation that will run:
   - bigconfig: `bigeye -w <profile> bigconfig plan -ip $TMPDIR -op $TMPDIR/plan/` (then `apply -auto_approve` on confirm)
   - imperative: `bigeye -w <profile> metric upsert -f <file> -t SIMPLE` per file

   On `edit`, apply changes and re-present until `y` or `n`.

5. Ensure the tracking tag exists:
   - `MCP_AVAILABLE=false`: per Step 7.B with `feature_name=monitor tagging`. Set `SKIP_TAGGING=true`. Continue.
   - `MCP_AVAILABLE=true`: `mcp__bigeye__list_tags` with `search: <deploy.tag>`. If absent, `mcp__bigeye__create_tag` (`name: <deploy.tag>`, `color_hex: "#6366F1"`). Store `tag_id`.

6. Create monitors.

   **bigconfig path:**
   1. `bigeye -w <profile> bigconfig plan -ip "$TMPDIR" -op "$TMPDIR/plan"`.
   2. Read plan report. Print `Plan: N create, M update, 0 errors.`
   3. Re-confirm: `Apply now? (y/n)`. On `n`, stop without writes.
   4. `bigeye -w <profile> bigconfig apply -ip "$TMPDIR" -auto_approve`.
   5. Read apply report. Extract created metric IDs.

   **imperative path:** for each YAML in `$TMPDIR`, run `bigeye -w <profile> metric upsert -f <file_path> -t SIMPLE`. Track success/failure. Parse output for created metric IDs.

7. Tag created monitors (skip if `SKIP_TAGGING=true`):
   For each successfully created monitor, `mcp__bigeye__tag_entity` with `tag_id`, `entity_id: <metric_id>`, `entity_type: METRIC`.

8. Render results:
   ```
   ## Deployment Results

   {success}/{total} monitors created successfully

   {if failures:}
   Failed:
   - {metric_type} on {column}: {error}

   Created monitor IDs: {ids}
   All monitors tagged with `{deploy.tag}` for tracking.
   {if SKIP_TAGGING: "Note: monitors were NOT tagged (MCP unavailable). Re-run after enabling MCP to backfill tags."}
   ```

9. Footer:
   ```
   Next: /bigeye-triage     (verify in ~1 hour)
   More: /bigeye-coverage {table}  ·  /bigeye-table {table}  ·  /bigeye-improve {table}
   ```

## State persistence

On successful apply (Step 6 success), follow `preamble.md` Step 8.B for the `bigeye-deploy` row:
- Set `state.json.last_table = "<fq>"` (when target was a table).
- Append `{ skill: "bigeye-deploy", at: <iso8601>, note: "<N monitors created>" }` to `state.json.tables[<fq>].actions`.
- Update `first_seen` / `last_seen`.

Then run pruning per Step 8.C. Failed deploys do not write state.

## Errors

| Condition | Behavior |
|---|---|
| MCP off + `gaps`/`bulk` | hard-fail per Step 7.B (no CLI equivalent for coverage) |
| MCP off + `columns` w/o `--metric-type` | hard-fail per Step 7.B with workaround |
| bigconfig plan errors | print plan errors verbatim; do not proceed to apply |
| imperative upsert partial failure | report success/fail counts; do not chain Next-action until fixed |
| Tag creation failure | continue; print warning; do NOT skip the monitor create |
