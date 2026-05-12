# BigEye Freeform Debug Mode — Design

**Status:** Draft
**Date:** 2026-05-12
**Owner:** Andrii Koziichuk
**Supersedes:** none. Extends `docs/spec.md` (`bigeye-investigate` v1).

## 1. Problem

`/bigeye-investigate` only accepts a BigEye issue ID (or URL). Many real debugging sessions start without a BigEye ticket: a developer notices weird numbers in a query result, a freshness lag they want to confirm, an unexplained gap in a chart. They want the same pack-driven, read-only Snowflake investigation engine pointed at a freeform description of the symptom — prose plus, optionally, the SQL query they were running.

Today there is no entry point for that. Users either fabricate a BigEye issue or skip the tool entirely.

## 2. Goals

1. Same command. `/bigeye-investigate` branches on the shape of its argument; users do not learn a second command.
2. Prose-first input. The user pastes a natural-language description of the issue and optionally a SQL block. The agent extracts what it can, asks for what it cannot, then runs the engine.
3. Reuse the existing engine, pack system, renderer, and `bigeye-investigator` subagent. No second subagent. No fork of the engine.
4. Reuse both output templates (memo + ticket body). They are already monitor-agnostic enough to render freeform results with one small template tweak.
5. Preserve the read-only invariant. Pasted SQL passes through `readonly_guard` like every other query.

## 3. Non-goals

- Closing FR-1.3 (SOV-only rejection from `docs/spec.md`). The v0.5 codebase already accepts non-SOV tables; freeform widens that further. Accepted scope drift, called out so reviewers see it explicitly.
- Shipping new pack content. Freeform falls back to `_default` when tag lookup fails. SOV-specific or domain-specific pack content is separate work under `/bigeye-pack`.
- An eval harness for SC-1. Out of scope for this design.
- Automated ticket creation, Slack delivery, or any other v2 item from `docs/spec.md` §2.

## 4. User-visible surface

### 4.1 Routing

The first positional arg classifier in `/bigeye-investigate`:

| Pattern | Mode | Notes |
|---|---|---|
| `^\d+$` or `--internal-id` flag | `issue` | Existing flow. Unchanged. |
| `^https?://.*bigeye\..*/issues/\d+` | `issue` | Existing URL parse. Unchanged. |
| empty arg + `state.json.last_issue` set | `issue` | Existing resume. Unchanged. |
| empty arg + `last_freeform_investigation` set + no `last_issue` | `freeform` | New: resume last freeform run. |
| anything else (contains spaces, text, fenced code block) | `freeform` | New path. |

Conservative rule: an ambiguous arg (e.g. `FOO.BAR`) routes to freeform because the issue path would 404 anyway.

### 4.2 New flags (freeform only)

- `--table <fq>` skips the table clarifying question.
- `--since <date|interval>` skips the filter clarifying question. Accepts ISO date (`2026-05-09`) or interval shorthand (`7d`, `24h`).
- `--type <freshness|volume|null|distribution|schema|custom>` skips issue-type inference.
- `--ticket` re-emits the ticket-body block (otherwise memo-only output by default).

Existing flags (`--pack`, `--snow`, `--budget`) work in both modes unchanged.

### 4.3 Example session

```
$ /bigeye-investigate "orders table looks empty for amazon since monday. ran this and got 0:
```sql
SELECT COUNT(*) FROM PROD.ORDERS WHERE retailer = 'amazon' AND loaded_at >= '2026-05-11'
```
"

Freeform investigation intake:
  Table:        PROD.ORDERS
  Filter:       loaded_at >= '2026-05-11'
  Issue type:   volume
  Pack:         _default (tag lookup empty)
  Budget:       10
  Seed query:   yes (will run as query #0)
Proceed? [y/n] y

[intake] freeform — synthesized D-7a3f
[query 1/10] seed :: COUNT(*) on PROD.ORDERS WHERE retailer = 'amazon'...
   → 0 rows
[hypothesis] ranked 3; top-3: upstream-filter-changed (prior=1.0), partial-load (prior=0.6), source-legitimately-decreased (prior=0.3)
... <engine continues>

## Investigation — D-7a3f
**Root cause:** Upstream WHERE filter changed _(medium confidence)_
...
```

## 5. Architecture

```
                        ┌─────────────────────────────────────────────┐
                        │  /bigeye-investigate skill (main thread)    │
                        │                                             │
   user arg ─────► [arg router] ─┬─► issue path (unchanged) ──┐       │
                                 │                            │       │
                                 └─► freeform path:           │       │
                                       F0 parse prose          │      │
                                       F1 clarifying Qs (≤3) ──┤      │
                                       F2 guard pasted SQL     │      │
                                       F3 confirm intake       │      │
                                       synthesize Request ─────┘      │
                                                                      │
                        └──────────────────────┬───────────────────────┘
                                               │ dispatch
                                               ▼
                        ┌─────────────────────────────────────────────┐
                        │  bigeye-investigator subagent (unchanged)    │
                        │  engine.md Phase 1 branches on request.mode  │
                        │  Phases 2–5 unchanged                        │
                        └──────────────────────┬───────────────────────┘
                                               │ result
                                               ▼
                        ┌─────────────────────────────────────────────┐
                        │  Renderer (memo + ticket templates)          │
                        │  one small template tweak; otherwise reused  │
                        └─────────────────────────────────────────────┘
```

### 5.1 Component boundaries

| Component | Responsibility | Owns |
|---|---|---|
| Arg router | Classify input as `issue` or `freeform`. No I/O. | First few lines of the skill `Procedure`. |
| Freeform intake | Parse prose, ask required-field questions, validate pasted SQL, confirm, synthesize `InvestigationRequest`. Main-thread only. | `references/freeform-intake.md` (new). |
| Engine | Phase 1 branches on `request.mode`. Phases 2–5 identical. | `references/engine.md` (edited). |
| Contracts | Document additive fields (`mode`, `intake_facts`, `seed_query`). | `references/contracts.md` (edited). |
| Renderer | Render seed-query trace row distinctly; wrap threshold line in `{{#threshold}}`. | `references/memo-template.md` (edited). |
| Guard | Unchanged. | `tools/readonly_guard.py`. |
| Subagent prompt | Unchanged. The agent follows engine.md, which now branches. | `agents/bigeye-investigator/AGENT.md`. |

### 5.2 Boundary tests
- Arg router has no Snowflake access and no MCP access. Pure string classification.
- Freeform intake has no Snowflake access. MCP access limited to `list_entity_tags` for pack auto-resolve, executed inside the subagent during Phase 1, not in the intake step.
- The engine never knows whether a request came from the issue path or the freeform path beyond inspecting `request.mode`. All downstream behavior reads from `issue_snapshot`, which is populated identically in both modes.

## 6. Prose intake routine

Lives in `skills/bigeye-investigate/references/freeform-intake.md`.

### 6.1 Phase F0 — Parse raw input

Single pass over the user's argument and flags. Best-effort extraction; not a parser.

- **Table candidates.** Regex `[A-Z_][A-Z0-9_]*\.[A-Z_][A-Z0-9_]*(\.[A-Z_][A-Z0-9_]*)?` matches `SCHEMA.TABLE` and `DB.SCHEMA.TABLE`. Plus `FROM <ident>` and `JOIN <ident>` from any fenced SQL block. Multiple matches are deduplicated. If exactly one survives, it becomes `table_fq`. If multiple, the first one mentioned in the SQL block wins; if no SQL, ask.
- **SQL block.** First ```` ```sql ... ``` ```` fence, or unfenced text starting with `SELECT` or `WITH` and ending at the next blank line.
- **Time hints.** Phrases `since <date|day|interval>`, `last N days/hours`, `between X and Y`, ISO dates. Normalize to a `monitor_where` candidate (`<time_col> >= '<iso>'`). `<time_col>` defaults to `loaded_at`; user can override with `column=<name>` syntax in the answer.
- **Column hints.** Backtick or quoted identifiers; phrases like `column FOO is null`.
- **Symptom keywords → tentative `issue_type`.**
  - "stale", "not updated", "since" + lag → `freshness`
  - "missing rows", "empty", "row count", "fewer rows" → `volume`
  - "null", "blank", "empty values" → `null`
  - "skewed", "distribution", "outlier", "spike", "drop in <metric>" → `distribution`
  - "column changed", "new column", "type" → `schema`
  - otherwise → `custom`

Flag overrides (`--table`, `--since`, `--type`) always win.

### 6.2 Phase F1 — Required-fields gate

Required for engine dispatch: `table_fq`, `monitor_where`, `issue_type`.

Up to **three** rounds of clarifying questions. Each round asks exactly one question, in this order:

1. If `table_fq` missing:
   ```
   Which table is this about? (e.g. SCHEMA.TABLE)
   ```
2. If `monitor_where` missing or extracted-but-low-confidence:
   ```
   What time window or filter scopes the issue? Options:
     [1] last 7 days   [2] last 24 hours   [3] all rows
     [4] enter custom WHERE clause
   Default time column: loaded_at — change with: column=<name>
   ```
3. If `issue_type` confidence low (no symptom keywords matched):
   ```
   Which kind of issue?
     [1] freshness  [2] volume  [3] null  [4] distribution  [5] schema  [6] custom
   ```

After three rounds, if any required field is still missing, the skill stops:

```
Error: not enough info to investigate.
Fix:   /bigeye-investigate "<your description>" --table SCHEMA.TABLE --since 7d --type volume
Why:   need table, time scope, and issue type to run hypotheses.
```

### 6.3 Phase F2 — Guard pasted SQL

If a SQL block was extracted, run `python -m tools.readonly_guard "<sql>"`. Non-zero exit:

```
Error: pasted SQL rejected by read-only guard: <reason>.
Fix:   remove the write statement and re-run.
```

Stop. No engine dispatch.

### 6.4 Phase F3 — Confirm intake

Print one block:

```
Freeform investigation intake:
  Table:        SCHEMA.TABLE
  Filter:       loaded_at >= '2026-05-05'
  Issue type:   volume
  Pack:         _default (tag lookup pending; resolved at engine Phase 2)
  Budget:       10
  Seed query:   yes (will run as query #0)
Proceed? [y/n]
```

- `y` → build `InvestigationRequest`, dispatch subagent.
- `n` → re-enter Phase F1 round 1, prior answers preserved.

## 7. Contract additions

`references/contracts.md` adds three optional fields to `InvestigationRequest`:

```jsonc
{
  // ... existing fields ...

  "mode": "issue" | "freeform",          // default "issue" when absent
  "intake_facts": {                      // null when mode == "issue"
    "table_fq": "SCHEMA.TABLE",
    "column": null,
    "monitor_where": "loaded_at >= '2026-05-05'",
    "issue_type": "volume",
    "time_column": "loaded_at",
    "opened_at": "<now iso>",
    "user_prose": "<original input verbatim>"
  },
  "seed_query": {                        // null when no SQL pasted
    "sql": "SELECT ...",
    "source": "user-pasted"
  }
}
```

`InvestigationResult` schema is unchanged. The `trace` array gains a `seed: true` boolean on the seed query event:

```jsonc
{
  "kind": "query",
  "hypothesis_id": "seed",
  "sql": "...",
  "row_count": 0,
  "ms": 320,
  "result_summary": "user query returned 0 rows",
  "rows_sample": [],
  "seed": true
}
```

The `issue_snapshot` shape is the same in both modes. In freeform mode, the engine populates it from `intake_facts` plus the seed query result.

## 8. Engine changes (`references/engine.md`)

### 8.1 Phase 1 branch

```
if request.mode == "freeform":
    1.1  internal_id = null; display_name = request.issue_ref
    1.2  issue = synthesize_issue_from_intake_facts(request.intake_facts)
    1.3  history = []                                  # no BigEye history
    1.4  profile = null                                # no BigEye profile
    1.5  lineage = null; upstream_issues = []
    1.6  related = []
    1.7  tags_table = BigeyeClient.get_tags(intake_facts.table_fq, "table")
         (best effort — empty on MCP failure)
         tags_source = []
else:
    # existing Phase 1, unchanged
```

`synthesize_issue_from_intake_facts` produces an `IssueDetails`-shaped object with BigEye-only fields set to `null` (`monitor_sql`, `threshold`, `current_value`, `severity`, `priority`, `status`). `metric_timeline` is set to `"Freeform investigation — no historical baseline."` unless the seed query result lets us write a one-line observation.

### 8.2 Seed query execution

Inserted at the start of Phase 3, before the hypothesis loop:

```
if request.seed_query and budget_used < budget:
    sql = request.seed_query.sql
    try:
        assert_readonly(sql)
    except GuardError as e:
        append { kind: "guard_reject", sql, reason: str(e), hypothesis_id: "seed" }
        # do not consume budget; continue without seed
    else:
        result = SnowClient.execute(sql, request.snow_profile)
        budget_used += 1
        append {
          kind: "query", hypothesis_id: "seed",
          sql, row_count: result.row_count, ms: result.ms,
          result_summary: LLM_summarize(result),
          rows_sample: result.rows[:50],
          seed: true,
          display_label: "user-provided query"
        }
        prior_evidence_seed = result      # feeds into LLM_score_evidence below
```

Hypothesis-query trace events gain the same `display_label` field, set to the hypothesis id. The renderer reads `display_label` directly; no template-side conditional. The seed query is the first executed query, so its `query_idx` in the rendered trace table is `1`. Pack-hypothesis queries follow as `2..N`.

The seed result becomes part of `prior_evidence` for `LLM_score_evidence(...)` calls on every subsequent hypothesis.

### 8.3 Phase 2 (pack resolve)

Unchanged. `tags = unique(tags_table + tags_source)` — in freeform mode `tags_source` is empty and `tags_table` is whatever `get_tags` returned. The override path (`--pack`) works identically.

### 8.4 Phase 4 (diagnose)

Unchanged. Confidence rubric applies the same way. Freeform diagnoses can hit `high` confidence when evidence supports it; the rubric does not require BigEye context.

### 8.5 Phase 5 (return)

Unchanged. Returns `InvestigationResult` with `issue_snapshot.display_name == request.issue_ref` (synthetic ID).

## 9. Renderer changes (`references/memo-template.md`)

### 9.1 Threshold line wrap

Wrap the existing line:

```
- Current value: {{issue_snapshot.current_value}} (threshold: {{issue_snapshot.threshold.kind}}={{issue_snapshot.threshold.value}})
```

in a section block so it disappears when `threshold` is null:

```
{{#issue_snapshot.threshold}}
- Current value: {{issue_snapshot.current_value}} (threshold: {{issue_snapshot.threshold.kind}}={{issue_snapshot.threshold.value}})
{{/issue_snapshot.threshold}}
```

### 9.2 Trace table — seed row

Existing row template:

```
| {{query_idx}} | `{{hypothesis_id}}` | {{kind}} | {{result_summary}} |
```

Replace with `display_label` (hydrated upstream by the engine — see §8.2):

```
| {{query_idx}} | {{display_label}} | {{kind}} | {{result_summary}} |
```

For pack-hypothesis queries `display_label` equals the hypothesis id wrapped in backticks; for the seed query it equals `_user-provided query_`. The seed's `query_idx` is `1` (first executed query); pack-hypothesis queries follow as `2..N`. The renderer does no per-row conditional.

### 9.3 Severity / priority / status

Stay visible, render `—` for null. Avoids template branching for fields that are commonly absent.

### 9.4 Header

`Investigation — {{display_name}}` already prefixes with whatever the engine passes. Freeform display_name is `D-<short>` (e.g. `D-7a3f`); the template needs no change.

### 9.5 Ticket body

Already monitor-agnostic per the commit that stripped BigEye specifics. No template change. `metric_timeline` falls back to the engine-hydrated string for freeform runs.

## 10. State persistence

`state.json` gains a new top-level key:

```jsonc
{
  // ... existing keys (last_issue, last_table, last_workflow, last_investigation, issues, ...)

  "last_freeform_investigation": {
    "synthetic_id": "D-7a3f",
    "table": "SCHEMA.TABLE",
    "request_id": "<uuid>",
    "at": "2026-05-12T20:55:00Z",
    "confidence": "medium",
    "pack_used": "_default",
    "issue_type": "volume",
    "monitor_where": "loaded_at >= '2026-05-05'",
    "trace_path": "~/.claude/bigeye-plugin/investigations/D-7a3f-2026-05-12T20-55-00Z.json"
  }
}
```

Resume rules:

| state.json state | Empty-arg behavior |
|---|---|
| `last_issue` set | Resume issue mode (existing). |
| `last_issue` empty, `last_freeform_investigation` set | Resume freeform — re-print intake confirmation, ask `Proceed? [y/n]`. |
| Both empty | Ask `Which issue?` (existing). |

`issues[<display_name>].actions` is **not** appended for freeform runs. Synthetic IDs do not enter the BigEye-issue history map. Reason: `/bigeye-roster`, `/bigeye-improve`, and friends key off real BigEye issue IDs.

Trace file path mirrors issue mode:

```
~/.claude/bigeye-plugin/investigations/<synthetic_id>-<iso8601>.json
```

Pruning rule from `preamble.md` Step 8.C applies to both kinds.

## 11. Read-only invariant

Unchanged. Two layers:

1. Layer 1 (engine-side): `assert_readonly` runs before every `snow sql`, including the seed query. The main-thread skill also runs the guard during Phase F2 for fail-fast UX, but the engine re-checks (defense in depth).
2. Layer 2 (Snowflake-side role): unchanged.

No code path bypasses the guard. Pasted SQL is no exception.

## 12. Error handling

Additions to the skill's `Errors` table:

| Condition | Block |
|---|---|
| Intake exhausts 3 rounds without `table_fq` | `Error: not enough info. Fix: /bigeye-investigate "<text>" --table SCHEMA.TABLE --since 7d --type volume. Why: need table, time scope, and issue type to run hypotheses.` |
| Pasted SQL fails read-only guard (main thread) | `Error: pasted SQL rejected by read-only guard: <reason>. Fix: remove the write statement and re-run.` Stop. |
| Pasted SQL fails read-only guard (engine; should not happen if main-thread check passed) | Append `guard_reject` trace event with `hypothesis_id: "seed"`; drop seed; engine continues with hypotheses. Budget NOT consumed. |
| User answers `n` to F3 confirmation | Re-enter F1 round 1, prior answers preserved. No state write. |
| Snowflake error executing seed | Append `snowflake_error`; drop seed result; engine continues. Budget IS consumed (engine attempted execute). |
| Seed returns 0 rows | Treat as valid result. `result_summary = "user query returned 0 rows"`. Continue. |
| Seed times out (>60s) | `snowflake_error` with timeout reason. Drop. Continue. Budget consumed. |
| Extracted table not found in Snowflake metadata | Warn line; continue (some warehouses block `INFORMATION_SCHEMA`). |
| Resume requested but trace file deleted | Print `Note: prior freeform trace removed; starting fresh intake.` Then F1 round 1. |

Existing error conditions (snow profile unconfigured, MCP unavailable for tag lookup, etc.) apply unchanged.

## 13. Testing

### 13.1 Unit
- `tests/test_readonly_guard.py` — already exists; runs verbatim. No new cases required by this design (seed query goes through the same guard).
- Add `tests/test_freeform_intake.py` covering Phase F0 extraction:
  - Table regex on prose vs. SQL block (single match, multiple matches, no match).
  - Time-hint normalization (`since monday`, `last 7 days`, ISO date, interval shorthand).
  - Symptom-keyword → issue_type mapping for each of the six types.
  - SQL extraction with fenced and unfenced inputs.
  - Flag-override precedence.

### 13.2 Integration
- `tests/test_freeform_e2e.py` (new) using fixture: prose input → synthesized `InvestigationRequest` → mocked subagent return → rendered memo. No live Snowflake or BigEye; mocked at adapter boundary. Covers:
  - Happy path: full intake from prose, no clarifying questions needed.
  - One clarifying question for missing time window.
  - Three clarifying questions exhausted; error path.
  - Pasted SQL rejected by guard.
  - Pasted SQL accepted; seed query executes; trace contains `seed: true` event.
  - State write: `last_freeform_investigation` set; `last_issue` untouched.

### 13.3 Manual smoke
- Run `/bigeye-investigate "rows missing on PROD.ORDERS since monday"` against the real environment. Expect intake confirmation with inferred filter and type, engine dispatch, memo with `D-<short>` header.

## 14. Files

### Touched
- `skills/bigeye-investigate/SKILL.md` — router table, freeform flags, new error rows, description-string widening (NFR-5 trigger phrasings).
- `skills/bigeye-investigate/references/contracts.md` — additive `mode`, `intake_facts`, `seed_query`; `seed: true` and `display_label` on `query` TraceEvent.
- `skills/bigeye-investigate/references/engine.md` — Phase 1 branch on `mode`; Phase 3 seed query block; `display_label` hydration.
- `skills/bigeye-investigate/references/memo-template.md` — threshold-line wrap; `display_label` in trace table.
- `agents/bigeye-investigator/AGENT.md` — note that the engine branches on `mode`; no new tools required.
- `skills/bigeye/references/preamble.md` — `last_freeform_investigation` in the §8.B state schema; per-skill writes row; no-arg fallback for `/bigeye-investigate` resume.

### New
- `skills/bigeye-investigate/references/freeform-intake.md` — Phases F0–F3, extraction regex catalog, clarifying-question copy, F3 confirmation block.
- `tests/test_freeform_intake.py`.
- `tests/test_freeform_e2e.py`.

### Untouched
- `tools/readonly_guard.py`.
- `skills/bigeye-pack/*`.
- `skills/bigeye-investigate/_default_pack/*`.

## 15. Open questions

- **Synthetic ID collision tolerance.** `D-<4-hex>` gives 65k IDs. Collisions within one user's history are unlikely but not impossible. Acceptable for v1; if a collision happens, the trace file write overwrites the older one. Mitigation deferred: extend to 8-hex if anyone hits it.
- **Time-column default of `loaded_at`.** This is an SOV-shop convention. Non-SOV tables may use `event_time`, `created_at`, etc. The intake question explicitly tells the user how to override (`column=<name>`), so the default is recoverable. Not closed; flagged for review.
- **Pack auto-resolve in freeform.** Today `tags_table` is fetched even when there is no BigEye issue. If `get_tags` is slow for many tables, freeform intake delays. Acceptable for v1; revisit if profiling shows it dominates.
- **`display_label` retrofit for issue mode.** §8.2 introduces a `display_label` field on `query` trace events for both issue and freeform modes. Existing issue-mode trace files written before this change will lack the field; the renderer must fall back to `hypothesis_id` when `display_label` is absent. Flagged as a small back-compat concern.
