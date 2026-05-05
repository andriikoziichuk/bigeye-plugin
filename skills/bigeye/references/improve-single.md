# Improve — single-monitor procedure

Used by `/bigeye-improve <monitor_id>`.

## Inputs

- `monitor_id` (int) — required
- profile (active or `--profile <name>`)
- custom hints scoped to the monitor or its table

## Procedure

1. Resolve monitor: `mcp__bigeye__get_table_metrics` filtered to `monitor_id` to fetch metric type, current threshold, table, column.
2. Gather profile + history:
   - `mcp__bigeye__get_table_profile(table_id, columns=[<col>])` — column distribution / null rate / cardinality / format samples / numeric range.
   - `mcp__bigeye__list_table_metrics(table_id)` filtered to `monitor_id` — last 30d runs.
   - Read `custom_hints` filtered by `(scope=monitor AND target_id=<monitor_id>)` OR `(scope=table AND target_id=<table_id>)`.
3. Generate candidate change. For threshold metrics, propose new bounds based on observed distribution + history. For regex/categorical, propose a tightened pattern grounded in actual values.
4. SQL refinement loop (max 3 iterations):
   1. Emit candidate validation SQL: a SELECT that would have flagged a row if the proposed threshold were active during the last 30d.
   2. Run the SQL via `mcp__bigeye__create_metric` dry-run mode if available, else fall back to documenting the SQL for the user to inspect.
   3. Count FP/FN against the existing closed-issues record for the monitor (`mcp__bigeye__search_issues(monitor_id, status=CLOSED)`).
   4. Adjust candidate to reduce FP+FN. Stop on convergence (FP+FN unchanged) or after iteration 3.
5. Render proposal — see template below. Read-only — never call create/update.

## Render template

```
{scope pill}
## Single-Monitor Improvement — Metric #{monitor_id}

Table:    {schema}.{table_name}
Column:   {column}
Type:     {metric_type}
Current:  {current_threshold_summary}
Proposal: {new_threshold_summary}

Why:
  • {one sentence per supporting fact, max 4 bullets}

Validation SQL (last 30d):
  ```sql
  {sql block, ≤ 25 lines}
  ```
  At proposed threshold: {FP} false positives, {FN} false negatives.
  At current threshold:  {FP_now} false positives, {FN_now} false negatives.

Custom hints applied:
  {bullet per matching hint, "(none)" if empty}

Source: {doc URL for this metric type}

Deploy:
  /bigeye-deploy monitor {monitor_id} --threshold {new_threshold_args}
```

The `Source:` line is filled by delegating to `bigeye-docs-grounding` with the metric type as the topic.

## Errors

- `monitor_id` not found → `Monitor #{id} not found in workspace. Fix: /bigeye-improve <table_name> to list monitors on a table.`
- Profile fetch partial fail → annotate the affected row `(profile unavailable)`. Continue.
- Validation SQL fails to run → emit the SQL anyway with `(SQL run failed — please verify manually)`. Skip FP/FN counts.
