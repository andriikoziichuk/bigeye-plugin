# Investigation Engine — pseudocode

The engine is a procedure any runtime can follow. v1 runtime is the `bigeye-investigator` subagent; v2 runtime will be a Python service. Both wire to the adapters defined in `adapters.md`.

Inputs and outputs are defined in `contracts.md`.

## State per run

```
trace          : ordered list of TraceEvent
budget_used    : int (incremented per executed Snowflake query, INCLUDING widening COUNT pre-checks)
hypotheses     : list ranked by (prior_weight × fits_issue_shape_score), updated with evidence
diagnosis      : { hypothesis_id, confidence, reasoning_md, suggested_next_steps_md, untested_alternatives[] }
manual_steps   : list[string] | null
```

## Phase 1 — Intake (no Snowflake; budget unused)

1.1  `internal_id, display_name = BigeyeClient.resolve(request.issue_ref, request.internal_id_flag)`.
     Append `{ "kind": "intake", "step": "resolve", "ok": true }`.
1.2  `issue = BigeyeClient.get_issue(internal_id)`.
     Capture metric_type, threshold, current_value, severity, opened_at, status, priority, monitor_sql, monitor_where.
1.3  `history = BigeyeClient.get_metric_history(internal_id, window=30)`.
1.4  `profile = BigeyeClient.get_table_profile(issue.table_fq)`.
1.5  `lineage = BigeyeClient.get_lineage(issue.table_fq, max_depth=5)`. `upstream_issues = BigeyeClient.get_upstream_issues(issue.table_fq)`.
1.6  `related = BigeyeClient.get_related_issues(internal_id, days=30)`.
1.7  `tags_table = BigeyeClient.get_tags(issue.table_id, "table")`. `tags_source = BigeyeClient.get_tags(issue.source_id, "source")`.

If a step fails after one retry, append `{ "kind": "intake_failed", "step": "...", "stderr": "..." }`. If `1.1` or `1.2` fail, return early with `confidence = "low"`. Other intake failures degrade — engine continues with whatever data was fetched.

## Phase 2 — Pack resolve (no Snowflake; budget unused)

2.1  `tags = unique(tags_table + tags_source)`.
2.2  `pack = PackLoader.resolve_pack_for_tags(tags, override=request.pack_override)`.
     - With `override`: load by name. Not found → hard error; return `confidence = "low"` with reason.
     - Without override: filter packs whose `tags:` intersect `tags`. Sort by `priority desc, name asc`. First match wins. Empty → `_default`.
2.3  `hypotheses = pack.hypotheses[issue.metric_type]`. Empty for that type → fall through to `_default` for that type only; append a trace note.
2.4  Apply `pack.budget` override if present and lower than `request.budget`. The minimum wins.
2.5  Append `{ "kind": "pack_resolve", "pack_name": pack.name, "tag_matched": "...", "hypothesis_count": len(hypotheses), "candidates": [...] }`.

## Phase 3 — Hypothesis loop (Snowflake; budget consumed)

**Initial ranking.** For each hypothesis `h`:

```
prior_weight = { "high": 1.0, "medium": 0.6, "low": 0.3 }[h.prior]
fits_score   = LLM_score_0_to_1(h.rationale + h.expected_signal, issue_facts)
h.weight     = prior_weight * fits_score
```

Sort hypotheses by `weight desc`. The "consider" threshold is `weight >= 0.2`.

**Loop:**

```
while budget_used < budget:
    h = next unconfirmed hypothesis with weight >= 0.2, in weight order
    if h is None: break

    # Render template
    sql = h.query_template
            .replace("{{table}}", issue.table_fq)
            .replace("{{column}}", issue.column or "")
            .replace("{{monitor_where}}", issue.monitor_where)

    # Widening pre-check
    if h.requires_widening:
        count_sql = build_count_query(h, widened_filters)
        try:
            assert_readonly(count_sql)    # via tools/readonly_guard.py
        except GuardError as e:
            append { kind: "guard_reject", sql: count_sql, reason: str(e) }
            consider abort if 3-in-a-row
            continue
        result = SnowClient.execute(count_sql, request.snow_profile)
        budget_used += 1
        append { kind: "count", hypothesis_id: h.id, sql: count_sql,
                 widened_filters: ..., row_estimate: result.rows[0][0] }
        if row_estimate > pack.widening_threshold:
            append { kind: "skipped", hypothesis_id: h.id,
                     reason: "widened row count exceeds threshold" }
            continue

    # Main query
    try:
        assert_readonly(sql)
    except GuardError as e:
        append { kind: "guard_reject", sql, reason: str(e) }
        consider abort if 3-in-a-row
        continue
    result = SnowClient.execute(sql, request.snow_profile)
    budget_used += 1
    append { kind: "query", hypothesis_id: h.id, sql, row_count: result.row_count,
             ms: result.ms, result_summary: LLM_summarize(result), rows_sample: result.rows[:50] }

    # Score
    score = LLM_score_evidence(h.expected_signal, result, h.prior_evidence)
    # score ∈ {"confirms", "contradicts", "inconclusive"}
    h.evidence.append({ "score": score, "query_idx": budget_used })

    # Re-rank others based on new evidence (LLM judgment, bounded re-rank)

    # Optional corroborator
    if score == "confirms" and h.confirms_count() < 2 and h.corroborators:
        # add the next corroborator as a new high-weight pseudo-hypothesis

    # Verification switch
    if pack.verification and pack.verification.matches(trace, h, result):
        manual_steps = render_steps(pack.verification.steps, trace_context)
        append { kind: "verification_switch", reason: "..." }
        break
```

## Phase 4 — Diagnose

Evidence-count rubric:

- **high** — exactly one hypothesis has `confirms_count >= 2` AND zero contradictions AND every other plausible hypothesis (those with `prior in {high, medium}` and `weight >= 0.2`) has at least one `contradicts` or `inconclusive` query against it.
- **medium** — one hypothesis has `confirms_count == 1` and zero contradictions.
- **low** — no single hypothesis dominates, OR `budget_exhausted`, OR every plausible hypothesis is untested.

Build `Diagnosis`:

```
{
  "hypothesis_id": top.id if top else None,
  "confidence": "high" | "medium" | "low",
  "reasoning_md": one-paragraph explanation citing the QueryEvent indices,
  "suggested_next_steps_md": markdown bullets — when confidence=high|medium derive from
                             top.playbook_link (if present) plus a "Confirm in BigEye" line;
                             when confidence=low list "Re-run with --budget <n+5>" and the
                             top 3 untested_alternatives as suggested probes,
  "untested_alternatives": [
    { "hypothesis_id": h.id, "why_untested": "budget exhausted" | "below threshold" | ... }
    for h in plausible hypotheses with no evidence
  ]
}
```

If `budget_used >= budget` and confidence ended at `low`, append `{ "kind": "budget_exhausted" }`.

## Phase 5 — Return

Return the full `InvestigationResult` per `contracts.md`. The frontend Renderer turns it into `memo_md` + `ticket_body_md`. Engine does NOT render.

## Error handling

| Condition | Engine response |
|---|---|
| BigEye `resolve` or `get_issue` fail | return early with `confidence = "low"` and `intake_failed` event |
| BigEye non-critical intake fails | degrade; continue with empty data; trace note |
| Pack file malformed | append `pack_error`; fall through to `_default`; continue |
| Pack override not found | return `confidence = "low"`; reason `"pack '<name>' not found"` |
| Snowflake query errors mid-loop | append `snowflake_error`; mark hypothesis untested; continue. Third consecutive auth error → abort |
| Guard rejects 3-in-a-row | `engine_abort`; return `confidence = "low"` |
| Budget exhausted | break loop; Phase 4 reports `confidence = "low"`; `budget_exhausted` event |
| Verification trigger matches | populate `manual_steps`; break loop; Phase 4 may still set high/medium confidence if evidence supports it |

## Read-only invariant

Every `SnowClient.execute()` call is preceded by `assert_readonly(sql)` via `tools/readonly_guard.py`. There is no override. Tests in `tests/test_readonly_guard.py` cover the guard. Two-layer defense (Snowflake role) is operational, not engine-enforced.
