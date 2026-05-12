Service Request Name: Data quality issue — {{dimension}} check failing on {{table_name}}{{#column_name}}.{{column_name}}{{/column_name}}
Product Category: [Select appropriate category]
Sub-Category: [Select appropriate sub-category]
Domain: [URL of the domain if the SR refers to a specific one]
Fields / Attribute: {{column_name}}

Description:
A {{dimension}} check on `{{schema_name}}.{{table_name}}`{{#column_name}}, column `{{column_name}}`,{{/column_name}} began failing on {{opened_at}} ({{time_since}}).

Expected: {{expected_value}}
Actual:   {{actual_value}}

Timeline:
{{metric_timeline}}

Downstream impact:
{{downstream_tables}}

Suggested resolution:
{{resolution_steps}}

SR Type: Problem/Incident
Severity: Medium
