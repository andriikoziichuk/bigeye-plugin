---
id: a-hypothesis
label: A label
rationale: because
prior: medium
expected_signal: a signal
query_template: |
  SELECT 1 FROM {{table}} WHERE {{monitor_where}}
---

id: another-hypothesis
label: Another label
rationale: because 2
prior: low
expected_signal: another signal
query_template: |
  SELECT 1 FROM {{table}} WHERE {{monitor_where}}
---
