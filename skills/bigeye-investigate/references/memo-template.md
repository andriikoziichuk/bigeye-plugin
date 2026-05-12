# Memo + Ticket Body Templates

Renderer reads this file and substitutes values from `InvestigationResult`. v1 emits markdown to chat; v2 (Slack/Jira) maps the same placeholders.

## Renderer hydration

The Renderer adapter does NOT just substitute fields from `InvestigationResult`. Before substitution, it hydrates a derived view that combines:

- `result.*` — every field on `InvestigationResult` from `contracts.md`.
- `diagnosis.hypothesis.*` — the full `HypothesisDef` from the pack, looked up by `result.diagnosis.hypothesis_id`. Provides `label`, `rationale`, `playbook_link`, `suggested_team`, etc.
- `trace.queries` — the subset of `result.trace` events with `kind: "query"`, numbered 1..N as `query_idx`.
- `snow_role` — read from the active BigEye profile's `snow.default_role` (see `/bigeye-config snow set`).
- `trace_path` — the filesystem path the skill writes the trace JSON to (`~/.claude/bigeye-plugin/investigations/<id>-<ts>.json`).
- `display_name` — convenience alias for `result.issue_snapshot.display_name`.

The hydrated view is passed to the substituter as a single flat dict (with dotted paths for nested access). Future renderers (Slack, Jira) hydrate the same derived view and produce different output formats.

## Memo template (`render_memo`)

```markdown
## Investigation — I-{{display_name}}

**Root cause:** {{diagnosis.hypothesis.label}} _({{diagnosis.confidence}} confidence)_

{{diagnosis.reasoning_md}}

### Issue context
- Table: `{{issue_snapshot.table_fq}}`
- Metric: `{{issue_snapshot.metric_type}}`{{#column}} on column `{{column}}`{{/column}}
- Severity: {{issue_snapshot.severity}} | Priority: {{issue_snapshot.priority}} | Status: {{issue_snapshot.status}}
- Opened: {{issue_snapshot.opened_at}}
- Current value: {{issue_snapshot.current_value}} (threshold: {{issue_snapshot.threshold.kind}}={{issue_snapshot.threshold.value}})
- Pack: `{{pack_used}}` | Snowflake role: `{{snow_role}}`

### Investigation trace
| # | Hypothesis | Action | Result |
|---|---|---|---|
{{#trace.queries}}
| {{query_idx}} | `{{hypothesis_id}}` | {{kind}} | {{result_summary}} |
{{/trace.queries}}

Budget: {{budget_used}}/{{request.budget}} queries used.

### Evidence
{{#diagnosis.hypothesis.playbook_link}}
{{playbook_link}}
{{/diagnosis.hypothesis.playbook_link}}

### Suggested next steps
{{#manual_steps}}
**Manual verification required.** Confidence remains low until verified:
{{#manual_steps}}- {{.}}
{{/manual_steps}}
{{/manual_steps}}
{{^manual_steps}}
{{diagnosis.suggested_next_steps_md}}
{{/manual_steps}}

### Untested alternatives
{{#diagnosis.untested_alternatives}}
- `{{hypothesis_id}}` — {{why_untested}}
{{/diagnosis.untested_alternatives}}
{{^diagnosis.untested_alternatives}}_(none — all plausible hypotheses tested)_{{/diagnosis.untested_alternatives}}
```

## Ticket-body template (`render_ticket_body`)

Plain markdown the user pastes into Jira or Asana with zero structural editing.

**Editorial rules:**
- No BigEye terminology, IDs, internal links, or product names. Describe the issue itself.
- No SQL queries or query traces. The ticket is for a non-engineer reader.
- Include a plain-English timeline of how the metric moved (dates + values), nothing more from the monitoring tool.

```markdown
**Title:** Data quality issue on `{{issue_snapshot.table_fq}}` — {{diagnosis.hypothesis.label}}

**Severity:** {{issue_snapshot.severity}}
**Suggested team:** {{diagnosis.hypothesis.suggested_team | default("data-platform")}}

## Summary
{{diagnosis.reasoning_md}}

## Affected data
- Table: `{{issue_snapshot.table_fq}}`{{#column}}
- Column: `{{column}}`{{/column}}
- First observed: {{issue_snapshot.opened_at}}

## Timeline
{{issue_snapshot.metric_timeline}}

## Diagnosis
**{{diagnosis.hypothesis.label}}** — confidence {{diagnosis.confidence}}

{{diagnosis.hypothesis.playbook_link}}

## Manual verification
{{#manual_steps}}
{{#manual_steps}}- [ ] {{.}}
{{/manual_steps}}
{{/manual_steps}}
{{^manual_steps}}_(none)_{{/manual_steps}}
```

Renderer note: `issue_snapshot.metric_timeline` is hydrated upstream by the engine using the same rules as `bigeye/references/improve.md` §1.0 (sort events, detect direction, render one short paragraph with absolute dates and the metric's own units). If `events[]` has fewer than 2 entries, hydrate as `Only one observation recorded ({{issue_snapshot.opened_at}}, value {{issue_snapshot.current_value}}).`

## Substitution rules

- `{{path.to.value}}` — direct lookup, empty string if absent.
- `{{#section}}...{{/section}}` — repeat block for each element if list, render once if truthy object, skip if null/empty.
- `{{^section}}...{{/section}}` — render only when section is falsy.
- `{{value | default("x")}}` — fallback value.
- `{{.}}` — current iteration value (used inside `{{#list}}`).

The renderer is a small string-substituter, not a full Mustache implementation. v1 implementation hand-rolls these five patterns. If a section requires logic beyond these, add a derived field upstream in the engine, not in the template.
