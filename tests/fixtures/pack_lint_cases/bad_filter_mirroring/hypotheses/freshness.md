---
id: no-filter-no-widening
label: Bad — drops monitor filter without setting requires_widening
rationale: x
prior: medium
expected_signal: x
query_template: |
  SELECT 1 FROM {{table}}
---

id: ok-second
label: Has filter mirroring
rationale: x
prior: low
expected_signal: x
query_template: |
  SELECT 1 FROM {{table}} WHERE {{monitor_where}}
---
