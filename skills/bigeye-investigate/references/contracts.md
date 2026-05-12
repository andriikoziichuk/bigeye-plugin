# Investigation Contracts

Schemas exchanged between the frontend (skill), the engine (pseudocode), and adapters. These are language-neutral — v1 wires Claude Code tools to them; v2 (Python service) implements the same shapes.

## InvestigationRequest

```jsonc
{
  "request_id": "uuid string",
  "issue_ref": "string — display name, internal id, or full BigEye URL",
  "internal_id_flag": false,
  "snow_profile": "named connection in ~/.snowflake/config.toml",
  "pack_override": null,                      // string or null
  "budget": 10,                                // int, ≥1
  "scope": {                                   // copied from active profile
    "data_sources": [],
    "schemas": [],
    "tables": [],
    "virtual_tables": []
  }
}
```

### Freeform-mode additions (optional)

Set on requests built by the freeform path. Absent on issue-mode requests; engine treats absence as `mode == "issue"`.

```jsonc
{
  // ... all existing fields ...
  "mode": "issue" | "freeform",
  "intake_facts": {
    "table_fq": "SCHEMA.TABLE",
    "column": null,
    "monitor_where": "loaded_at >= '2026-05-05'",
    "issue_type": "volume",
    "time_column": "loaded_at",
    "opened_at": "2026-05-12T20:55:00Z",
    "user_prose": "<original input verbatim>"
  },
  "seed_query": {
    "sql": "SELECT ...",
    "source": "user-pasted"
  }
}
```

`intake_facts` is required when `mode == "freeform"`. `seed_query` is optional.

## InvestigationResult

```jsonc
{
  "request": { /* InvestigationRequest verbatim */ },
  "issue_snapshot": {
    "internal_id": 42,
    "display_name": "I-10921",
    "metric_type": "volume",
    "table_fq": "SCHEMA.TABLE",
    "column": null,
    "monitor_where": "loaded_at >= DATEADD(day, -7, CURRENT_DATE)",
    "monitor_sql": "...",
    "threshold": { "kind": "min", "value": 1000 },
    "current_value": 312,
    "severity": "MAJOR",
    "opened_at": "2026-05-11T08:00:00Z",
    "status": "NEW",
    "priority": "P2",
    "tags_table": ["sov"],
    "tags_source": [],
    "event_history": [
      { "timestamp": "2026-05-04T08:00:00Z", "value": 1100 },
      { "timestamp": "2026-05-11T08:00:00Z", "value": 312 }
    ],
    "metric_timeline": "From May 4 the row count fell from ~1,100 to 312 by May 11 and has stayed depressed since."
  },
  "pack_used": "sov",
  "trace": [ /* list of TraceEvent — see TraceEvent below */ ],
  "diagnosis": {
    "hypothesis_id": "amazon-category-restructure",
    "confidence": "high",                      // high | medium | low
    "reasoning_md": "markdown explaining the call",
    "suggested_next_steps_md": "- bullet 1\n- bullet 2",
    "untested_alternatives": [
      { "hypothesis_id": "competitor-entry", "why_untested": "budget exhausted" }
    ]
  },
  "manual_steps": null,                        // list[string] or null
  "budget_used": 6,
  "budget_remaining": 4
}
```

## TraceEvent (tagged union)

Every trace event has a `kind` field naming its variant.

```jsonc
// kind: "intake"
{ "kind": "intake", "step": "issue_fetch", "ok": true, "ms": 142 }

// kind: "pack_resolve"
{ "kind": "pack_resolve", "pack_name": "sov", "tag_matched": "sov",
  "hypothesis_count": 6, "candidates": ["sov", "_default"] }

// kind: "pack_error"
{ "kind": "pack_error", "path": "~/.claude/bigeye-plugin/packs/sov/pack.yaml",
  "reason": "missing 'tags' field" }

// kind: "count"
{ "kind": "count", "hypothesis_id": "amazon-category-restructure",
  "sql": "SELECT COUNT(*) ...", "widened_filters": ["dropped date filter"],
  "row_estimate": 8200000 }

// kind: "query"
{ "kind": "query", "hypothesis_id": "amazon-category-restructure",
  "display_label": "`amazon-category-restructure`",     // hydrated by engine
  "sql": "SELECT ...", "row_count": 12, "ms": 1820,
  "result_summary": "12 categories, top has 0 rows in last 7 days",
  "rows_sample": [ { "category_id": "...", "rows": 0 } ],
  "seed": false                                          // true only for seed query
}
```

`display_label` is rendered verbatim in the memo trace table. For pack hypotheses the engine sets it to `` `<hypothesis_id>` `` (backtick-wrapped). For the seed query the engine sets it to `_user-provided query_`. Older trace files written before this field existed are rendered by falling back to `hypothesis_id`.

```jsonc
// kind: "skipped"
{ "kind": "skipped", "hypothesis_id": "...", "reason": "widened row count exceeds threshold" }

// kind: "guard_reject"
{ "kind": "guard_reject", "sql": "...", "reason": "forbidden keyword 'drop'" }

// kind: "snowflake_error"
{ "kind": "snowflake_error", "sql": "...", "stderr": "..." }

// kind: "verification_switch"
{ "kind": "verification_switch", "reason": "playbook_link triggered manual verification" }

// kind: "budget_exhausted"
{ "kind": "budget_exhausted" }

// kind: "engine_abort"
{ "kind": "engine_abort", "reason": "3 consecutive guard rejects" }

// kind: "intake_failed"
{ "kind": "intake_failed", "step": "...", "stderr": "..." }
```

## Confidence enum

`"high" | "medium" | "low"`. Rubric in `engine.md` Phase 4.
