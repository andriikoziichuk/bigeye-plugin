# Schema hypotheses — _default

---
id: column-added-upstream
label: New column added upstream
rationale: |
  Upstream system added a column; BigEye flagged the schema change.
prior: high
expected_signal: |
  INFORMATION_SCHEMA shows a new column not previously present.
query_template: |
  SELECT column_name, data_type
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE table_schema || '.' || table_name = UPPER('{{table}}')
  ORDER BY ordinal_position
requires_widening: true
---

id: column-removed-upstream
label: Column removed upstream
rationale: |
  Upstream system dropped a column.
prior: medium
expected_signal: |
  INFORMATION_SCHEMA missing a column we expected.
query_template: |
  SELECT column_name, data_type
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE table_schema || '.' || table_name = UPPER('{{table}}')
  ORDER BY ordinal_position
requires_widening: true
---
