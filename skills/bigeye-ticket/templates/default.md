Service Request Name: BigEye #{{issue_display_name}} — {{dimension}} on {{table_name}}.{{column_name}}
Product Category: [Select appropriate category]
Sub-Category: [Select appropriate sub-category]
Domain: [URL of the domain if the SR refers to a specific one]
Fields / Attribute: {{column_name}}
Description:
{{dimension}} check failed on `{{schema_name}}.{{table_name}}` ({{data_source}}).
Metric: {{metric_type}} ({{metric_name}}).

Expected: {{expected_value}}
Actual: {{actual_value}}
First failing event: {{opened_at}} ({{time_since}})

Event history:
{{event_history}}

Downstream impact:
{{downstream_tables}}

Related issues:
{{related_issues}}

Suggested first-look query:
{{sample_query}}

Resolution guidance:
{{resolution_steps}}

Reference: BigEye issue #{{issue_display_name}} ({{bigeye_url}})

SR Type: Problem/Incident
Severity: Medium
