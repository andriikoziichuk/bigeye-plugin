# Custom-metric hypotheses — _default

---
id: business-rule-violation
label: Business rule violation in source data
rationale: |
  Custom metrics encode business rules. A breach usually means the rule
  was violated in real data — not a metric bug.
prior: medium
expected_signal: |
  Run the same logic as the monitor SQL and inspect the rows that violate
  the rule.
query_template: |
  SELECT *
  FROM {{table}}
  WHERE {{monitor_where}}
  LIMIT 50
requires_widening: false
---
