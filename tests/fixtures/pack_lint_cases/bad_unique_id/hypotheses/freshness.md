---
id: same-id
label: First
rationale: x
prior: medium
expected_signal: x
query_template: |
  SELECT 1 FROM {{table}} WHERE {{monitor_where}}
---

id: same-id
label: Second
rationale: x
prior: low
expected_signal: x
query_template: |
  SELECT 1 FROM {{table}} WHERE {{monitor_where}}
---
