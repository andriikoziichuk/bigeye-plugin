# Freshness hypotheses — _default

---
id: upstream-loader-stalled
label: Upstream loader stalled or hung
rationale: |
  The most common freshness failure is the upstream ETL job stopped running
  or hung mid-batch. The table itself is fine; new rows simply aren't arriving.
prior: high
expected_signal: |
  MAX(loaded_at) is older than the monitor's expected freshness window. No new
  inserts in the last N hours where N >= the threshold. Other tables loaded
  by the same job also show staleness.
query_template: |
  SELECT
    MAX(loaded_at) AS last_load_at,
    COUNT(*) AS rows_total,
    DATEDIFF('hour', MAX(loaded_at), CURRENT_TIMESTAMP()) AS hours_since_last_load
  FROM {{table}}
  WHERE {{monitor_where}}
requires_widening: false
playbook_link: |
  Ticket the team that owns the loader. Include `last_load` and the expected
  cadence from the monitor.
---

id: scheduler-skipped
label: Scheduler skipped this run (cron misfire, dependency wait)
rationale: |
  Airflow / dbt / cron sometimes skip a run due to dependency blocks or
  paused DAGs. Table is healthy except for the gap.
prior: medium
expected_signal: |
  Loader is otherwise healthy — previous runs landed on time, future runs
  will resume. Single gap in `loaded_at` distribution.
query_template: |
  SELECT
    DATE_TRUNC('hour', loaded_at) AS hr,
    COUNT(*) AS rows
  FROM {{table}}
  WHERE {{monitor_where}}
  GROUP BY 1
  ORDER BY 1 DESC
  LIMIT 72
requires_widening: false
---

id: source-stopped-emitting
label: Source system stopped emitting
rationale: |
  Source-side outage. Loader runs fine but reads empty batches.
prior: medium
expected_signal: |
  Loader logs healthy (out of scope); newest rows in the table have
  expected loaded_at but unusually low row counts per batch.
query_template: |
  SELECT
    DATE_TRUNC('hour', loaded_at) AS hr,
    COUNT(*) AS rows
  FROM {{table}}
  WHERE {{monitor_where}}
  GROUP BY 1
  ORDER BY 1 DESC
  LIMIT 72
requires_widening: false
---
