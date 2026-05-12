# Null-rate hypotheses — _default

---
id: upstream-column-rename
label: Upstream column was renamed or removed
rationale: |
  An upstream change renamed or dropped the column, causing the ETL to
  load nulls in its place.
prior: high
expected_signal: |
  Null rate on the affected column jumped to ~100% at a discrete timestamp.
  Other columns unaffected.
query_template: |
  SELECT
    DATE_TRUNC('hour', loaded_at) AS hr,
    SUM(CASE WHEN {{column}} IS NULL THEN 1 ELSE 0 END) * 1.0 / NULLIF(COUNT(*), 0) AS null_rate,
    COUNT(*) AS rows
  FROM {{table}}
  WHERE {{monitor_where}}
  GROUP BY 1
  ORDER BY 1 DESC
  LIMIT 72
requires_widening: false
---

id: schema-mismatch
label: ETL schema mismatch — column type changed
rationale: |
  Type coercion failed and the loader wrote nulls.
prior: medium
expected_signal: |
  Null rate is elevated but not 100% — only rows with the new type are
  affected.
query_template: |
  SELECT
    {{column}} AS sample_value,
    COUNT(*) AS rows
  FROM {{table}}
  WHERE {{monitor_where}}
    AND {{column}} IS NOT NULL
  GROUP BY 1
  ORDER BY 2 DESC
  LIMIT 20
requires_widening: false
---

id: etl-drop-too-aggressive
label: ETL drop / filter step too aggressive
rationale: |
  A recent ETL change dropped rows that previously had real values, leaving
  only rows with null in this column.
prior: medium
expected_signal: |
  Null rate up AND row count down — the rows with values are the ones that
  got dropped.
query_template: |
  SELECT
    COUNT(*) AS rows_now,
    SUM(CASE WHEN {{column}} IS NULL THEN 1 ELSE 0 END) AS rows_null
  FROM {{table}}
  WHERE {{monitor_where}}
requires_widening: false
---
