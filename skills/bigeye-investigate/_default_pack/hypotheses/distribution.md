# Distribution hypotheses — _default

---
id: new-value-introduced
label: A new value entered the distribution
rationale: |
  An upstream source added a new category/code/enum that the monitor
  didn't expect.
prior: high
expected_signal: |
  Distribution histogram has a new bucket with non-trivial weight.
query_template: |
  SELECT
    {{column}} AS val,
    COUNT(*) AS rows
  FROM {{table}}
  WHERE {{monitor_where}}
  GROUP BY 1
  ORDER BY 2 DESC
  LIMIT 50
requires_widening: false
---

id: value-disappeared
label: An expected value disappeared
rationale: |
  An upstream source stopped producing one of the expected values.
prior: medium
expected_signal: |
  A previously-frequent value drops to zero in the recent window while
  others stay stable.
query_template: |
  SELECT
    {{column}} AS val,
    COUNT(*) AS rows
  FROM {{table}}
  WHERE {{monitor_where}}
  GROUP BY 1
  ORDER BY 2 DESC
  LIMIT 50
requires_widening: false
---
