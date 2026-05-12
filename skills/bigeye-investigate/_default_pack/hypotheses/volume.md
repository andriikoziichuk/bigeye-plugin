# Volume hypotheses — _default

---
id: upstream-filter-changed
label: Upstream WHERE filter changed
rationale: |
  An upstream view or ETL step added/changed a filter, dropping rows from
  this table even though the source data is intact.
prior: high
expected_signal: |
  Total row count dropped but the distribution of remaining rows looks
  consistent with a filter being applied (e.g., one partition or one value
  is now zero).
query_template: |
  SELECT COUNT(*) AS rows_now
  FROM {{table}}
  WHERE {{monitor_where}}
requires_widening: false
---

id: partial-load
label: Partial load — batch failed mid-run
rationale: |
  Loader started a batch but errored partway through. Some rows landed,
  some didn't.
prior: medium
expected_signal: |
  Row count is below expected but non-zero. `loaded_at` distribution shows
  a truncated tail at the most recent run.
query_template: |
  SELECT
    MAX(loaded_at) AS last,
    COUNT(*) AS rows,
    COUNT(DISTINCT DATE_TRUNC('hour', loaded_at)) AS hours_covered
  FROM {{table}}
  WHERE {{monitor_where}}
requires_widening: false
---

id: source-legitimately-decreased
label: Source data legitimately decreased
rationale: |
  No bug — the upstream system actually has less data (e.g., end of season,
  customer dropped, calendar effect).
prior: low
expected_signal: |
  Row count drop matches a similar drop in a related source-side metric.
  Distribution looks normal otherwise.
query_template: |
  SELECT
    DATE_TRUNC('day', loaded_at) AS day,
    COUNT(*) AS rows
  FROM {{table}}
  WHERE {{monitor_where}}
  GROUP BY 1
  ORDER BY 1 DESC
  LIMIT 60
requires_widening: false
---
