# BigEye DQ Investigator — Design Doc

**Status:** Approved for implementation
**Date:** 2026-05-12
**Spec input:** `docs/spec.md` (Requirements: Bigeye DQ Investigator Agent)
**Approach:** Subagent-dispatched investigation engine, ships as plugin skills, extractable to a standalone service later

---

## 1. Summary

A new BigEye plugin command `/bigeye-investigate <issue>` that takes a BigEye data quality issue, runs an automated read-only Snowflake investigation against a hypothesis playbook, and returns a confidence-rated resolution memo with a ready-to-paste ticket body.

Key shape changes from the spec:

- **Generic across all BigEye users, not SOV-only.** The investigation engine is generic. Domain knowledge (failure patterns, playbooks, manual verification steps) lives in pluggable "packs" loaded by BigEye tag on the table or source. SOV becomes the first pack — not a hard scope restriction.
- **Snowflake `snow` CLI, not MCP.** Spec §3.3 / §5 said Snowflake MCP. We use the modern `snow` CLI via Bash so read-only role grants are enforceable per Snowflake connection and `snow connection test` gives us a deterministic auth check.
- **Subagent-dispatched investigation loop.** `/bigeye-investigate` runs in the main thread; the 10-query investigation loop runs in a dedicated subagent (`bigeye-investigator`). Memo render returns to main thread. This isolates ~10 query result blobs from the user's main context and gives us the same dispatch shape we need for v1.1 parallel multi-issue.
- **Designed for extraction.** Engine procedure lives in standalone reference docs that read as pseudocode. Adapter contracts are explicit. v1 wires Claude Code tools to those adapters; v2 (deployment as an autonomous service) implements the same contracts in Python without rewriting investigation logic.

The investigator is **advisory and read-only**. It never modifies BigEye issues, never writes to Snowflake, and never creates Jira/Asana tickets directly — it produces the ticket body and the developer pastes.

## 2. Architecture

### 2.1 Layered design

```
┌─────────────────────────────────────────────────────────┐
│  Frontend                                               │
│   today: /bigeye-investigate skill (Claude Code)        │
│   future: webhook receiver, scheduled poller,           │
│           Slack bot, CLI, REST service                  │
└───────────────────────┬─────────────────────────────────┘
                        │ InvestigationRequest
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Investigation Engine (portable)                        │
│   intake → pack resolve → hypothesis loop → diagnose    │
│   confidence rubric, budget, read-only guard            │
│   returns InvestigationResult (structured)              │
└───┬──────────┬──────────┬──────────┬────────────────────┘
    │          │          │          │
    ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Bigeye  │ │Snow    │ │Pack    │ │Renderer│
│Client  │ │Client  │ │Loader  │ │        │
└────────┘ └────────┘ └────────┘ └────────┘

v1 impls (skill-side):
  Bigeye   → bigeye CLI + MCP tools via Bash
  Snow     → `snow sql -c <profile> --format json` via Bash
  Pack     → filesystem read of ~/.claude/bigeye-plugin/packs/
  Renderer → markdown emitted to Claude Code chat

v2 impls (server-side, swappable later):
  Bigeye   → direct REST client (token from env)
  Snow     → snowflake-connector-python
  Pack     → git clone / S3 / config map
  Renderer → Slack blocks / Jira REST / email
```

### 2.2 File layout

**Plugin repo additions (`bigeye-plugin/`):**

```
skills/
  bigeye-investigate/
    SKILL.md                    # user-invocable, thin orchestrator
    references/
      engine.md                 # portable investigation procedure
      contracts.md              # InvestigationRequest / Result schemas
      adapters.md               # Bigeye/Snow/Pack/Renderer interfaces
      memo-template.md          # markdown memo + ticket body templates
      readonly-guard.md         # SQL keyword denylist + checks
    _default_pack/              # ships generic fallback pack
      pack.yaml
      hypotheses/{freshness,volume,null,distribution,schema,custom}.md
      verification.md
  bigeye-pack/
    SKILL.md                    # /bigeye-pack new <name>, lint, list
    templates/
      pack.yaml.tmpl
      hypothesis.md.tmpl
      verification.md.tmpl
agents/
  bigeye-investigator/
    AGENT.md                    # subagent prompt + tool allowlist
```

**External (per-user, not in repo):**

```
~/.claude/bigeye-plugin/
  profiles.json                 # existing — adds `snow.profile`, `snow.default_warehouse`, `snow.default_role`
  packs/
    sov/                        # first user-authored pack
      pack.yaml
      hypotheses/{freshness,volume,null,distribution,schema,custom}.md
      verification.md
    _default/                   # copied from plugin on first run if absent
      ...
  state.json                    # existing — adds `last_investigation`
  investigations/               # NEW: per-run trace archive
    <issue_id>-<iso8601>.json   # full InvestigationResult, durable record
```

### 2.3 Skill split

| Skill | Surface | Purpose |
|---|---|---|
| `/bigeye-investigate <issue>` | user-invocable | Run an investigation. Dispatches the subagent. Renders the memo. |
| `/bigeye-pack new <name>` | user-invocable | Scaffold a new pack interactively. Includes `lint`, `list` subcommands. |
| `/bigeye-roster` (existing, extended) | user-invocable | Adds `[v]` investigate action; hands off to `/bigeye-investigate`. |
| `/bigeye-config snow ...` (existing, extended) | user-invocable | Configure the Snowflake profile per BigEye profile. Includes `verify`. |
| `bigeye-investigator` | subagent | Runs the engine in isolation. Returns a single JSON object. |

### 2.4 Portability discipline

To keep the engine extractable to a future Python service without rewriting investigation logic, the following discipline holds in v1:

- Investigation procedure lives in `engine.md` as plain pseudocode. No "use the Bash tool", no "render to chat".
- Adapter contracts in `adapters.md` define `BigeyeClient`, `SnowClient`, `PackLoader`, `Renderer` interfaces. v1 implementations are the skill's tool bindings.
- `InvestigationRequest` and `InvestigationResult` schemas in `contracts.md`.
- Pack files (`pack.yaml`, `hypotheses/*.md`, `verification.md`) are content-only — no Claude Code keywords.
- State writes and rendering happen frontend-side, not in the engine.

## 3. Investigation engine

`references/engine.md` — pseudocode any runtime can follow.

### 3.1 Inputs / outputs

```
InvestigationRequest:
  issue_ref           : str  (display name, internal id, or URL)
  internal_id_flag    : bool (skip display-name resolve)
  snow_profile        : str  (named connection in ~/.snowflake/config.toml)
  pack_override       : str? (force a pack by name)
  budget              : int  (default 10)
  scope               : ScopeBlock (from profiles.json)
  request_id          : str  (uuid)

InvestigationResult:
  request               : InvestigationRequest
  issue_snapshot        : { metric_type, table, column?, monitor_where, ... }
  pack_used             : str
  trace                 : list[TraceEvent]
  diagnosis             : { hypothesis_id, confidence, reasoning_md, untested_alternatives[] }
  manual_steps          : list[str]?  (populated only on verification switch)
  budget_used           : int
  budget_remaining      : int
  # memo_md / ticket_body_md NOT in engine output — rendered by frontend Renderer
```

### 3.2 Phases

**Phase 1 — Intake.** No Snowflake calls. Resolve `issue_ref` to internal id, fetch full issue (metric, threshold, current value, severity, opened_at, status, priority, monitor SQL, monitor WHERE clauses), metric history (last 30 runs), table profile, upstream lineage + open upstream issues, related issues on the same table within 30 days, and BigEye tags on the issue's table and source.

**Phase 2 — Pack resolve.** No Snowflake calls. Collect tags from the table and source. Load every `pack.yaml` under `~/.claude/bigeye-plugin/packs/*/`. Filter packs whose `tags:` intersect issue tags. Sort by `priority` desc, then name asc. First match wins. No match falls back to `_default` pack with a trace note. Explicit `pack_override` skips the tag match and loads by name (hard error if not found). Apply pack `budget` override if present.

**Phase 3 — Hypothesis loop.** Snowflake calls happen here. Initial ranking: hypotheses ranked by `prior: high|medium|low` declared in the pack, multiplied by a "fits-issue-shape" score (0..1) the LLM produces by reading each hypothesis's `rationale` + `expected_signal` against the actual issue facts (metric type, monitor SQL, drop magnitude, partition keys, retailer/dimension values, recent profile deltas). Example: for a volume issue showing a 60% drop scoped to `retailer='amazon'`, the `amazon-category-restructure` hypothesis scores ~0.9 because its `expected_signal` describes exactly that shape; `competitor-entry` scores ~0.3 because its signal expects gradual decline across retailers.

Loop while `budget_used < budget`:

1. Pick the next unconfirmed hypothesis above the "consider" threshold. None left → break (insufficient signal).
2. Render `query_template` with `{{table}}`, `{{monitor_where}}`, `{{column}}` substituted. Filters MIRROR the monitor by default — pack templates MUST start with the monitor's WHERE block.
3. If `requires_widening: true`, run a `SELECT COUNT(*)` pre-check with the widened filters. Append `CountEvent`. If `row_estimate > pack.widening_threshold` (default 10M), mark the hypothesis as `SkippedEvent { reason: "widened row count exceeds threshold" }` and continue. Budget consumed.
4. Run the main query through `SnowClient.execute` with the read-only guard. Budget consumed. Append `QueryEvent { hypothesis_id, sql, row_count, result_summary, rows_sample }`.
5. LLM scores the result against `expected_signal` as `confirms | contradicts | inconclusive`. Update hypothesis evidence. Possibly demote or promote other hypotheses.
6. Adaptive follow-up: if `score == confirms` but corroboration < 2, optionally run a follow-up from `corroborators[]`.
7. Manual-verification switch: if `pack.verification.triggers` match the current trace, populate `manual_steps`, append `VerificationSwitchEvent`, break.

**Phase 4 — Diagnose.** Evidence-count rubric:

- **high** — exactly one hypothesis has ≥2 confirming queries AND no contradicting evidence AND every other plausible hypothesis (`prior: high|medium`) has at least one ruling-out query.
- **medium** — one hypothesis has 1 confirming query, no contradictions.
- **low** — no single hypothesis dominates, OR budget exhausted, OR every plausible hypothesis untested.

`Diagnosis` is built with `hypothesis_id`, confidence, reasoning markdown, and a list of untested alternatives.

**Phase 5 — Return.** Engine returns `InvestigationResult`. Frontend Renderer turns the structured result into `memo_md` + `ticket_body_md`.

### 3.3 Trace events

```
TraceEvent = oneOf(
  IntakeEvent              { kind, bigeye_payload_refs },
  PackResolveEvent         { pack_name, tag_matched, hypothesis_count, candidates[] },
  PackErrorEvent           { path, reason },
  CountEvent               { hypothesis_id, sql, widened_filters, row_estimate },
  QueryEvent               { hypothesis_id, sql, row_count, result_summary, rows_sample },
  SkippedEvent             { hypothesis_id, reason },
  GuardRejectEvent         { sql, reason },
  SnowflakeErrorEvent      { sql, stderr },
  VerificationSwitchEvent  { reason },
  BudgetExhaustedEvent     {},
  EngineAbortEvent         { reason },
)
```

The trace is the durable artifact. Persisted verbatim to `~/.claude/bigeye-plugin/investigations/<issue_id>-<iso8601>.json`. Included in the memo "Investigation trace" section. Reproducible by any human running the same SQL.

## 4. Pack format

Three-file contract in `~/.claude/bigeye-plugin/packs/<name>/`.

### 4.1 `pack.yaml`

```yaml
name: sov
version: 1
priority: 50               # tiebreaker when multiple packs match. Higher wins.
description: Share-of-Voice tables across retailer sites
tags:                      # any tag match selects this pack
  - sov
  - share-of-voice
  - retail-sov
budget: 10                 # max Snowflake queries per investigation
widening_threshold: 10000000   # COUNT-estimated rows above which widened queries skip
covers:                    # issue types this pack covers
  - freshness
  - volume
  - null
  - distribution
  - schema
  - custom
```

### 4.2 `hypotheses/<issue_type>.md`

One file per issue type listed in `covers`. Markdown with YAML front-matter blocks separated by `---`.

**HypothesisDef fields:**

| Field | Required | Purpose |
|---|---|---|
| `id` | yes | Stable slug. Referenced from trace and memo. |
| `label` | yes | One-line human title. Appears in memo. |
| `rationale` | yes | Why this hypothesis exists. LLM uses it when ranking. |
| `prior` | yes | `high` / `medium` / `low`. Initial weight before evidence. |
| `expected_signal` | yes | What a confirming result looks like. LLM matches result against this. |
| `query_template` | yes | Jinja-style template. `{{table}}`, `{{monitor_where}}`, `{{column}}` substituted by engine. |
| `requires_widening` | no | Default false. True → engine runs COUNT pre-check before main query. |
| `corroborators` | no | List of follow-up queries for confidence escalation. Same shape. |
| `playbook_link` | no | Markdown block included in memo when this hypothesis is the diagnosis. |

**Authoring rule:** `query_template` MUST either contain `{{monitor_where}}` substitution OR set `requires_widening: true`. Pack lint enforces this — otherwise filter mirroring is silently bypassed.

### 4.3 `verification.md`

Optional. Triggers for switching to manual retailer-verification mode (FR-3.6), plus the steps template the engine renders. Plain markdown with `## Triggers`, `## Steps template`, `## Output` sections.

### 4.4 `_default` pack

Ships in the plugin repo at `skills/bigeye-investigate/_default_pack/` (directory name differs from the user-side `_default/` so a repo `grep` distinguishes the shipped source from the per-user copy). Copied to `~/.claude/bigeye-plugin/packs/_default/` on first run if absent. Contains generic hypotheses per issue type with no domain specifics. Always has `priority: 0`, always loses to any user-authored pack.

## 5. `/bigeye-investigate` skill

### 5.1 Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `<display_name>` | Investigate issue by BigEye display ID | `/bigeye-investigate 10921` |
| `<url>` | Investigate from full BigEye issue URL | `/bigeye-investigate https://app.bigeye.com/issues/10921` |
| `<id> --internal-id` | Bypass display-name lookup | `/bigeye-investigate 42 --internal-id` |
| (no arg) | Resume `state.json.last_issue`; else prompt | `/bigeye-investigate` |
| `--pack <name>` | Force pack override | `/bigeye-investigate 10921 --pack sov` |
| `--snow <profile>` | Override stored `snow.profile` | `/bigeye-investigate 10921 --snow ro-analytics` |
| `--budget <n>` | Override pack/default budget | `/bigeye-investigate 10921 --budget 15` |

### 5.2 Main-thread procedure

```
1. Follow skills/bigeye/references/preamble.md Steps 1–7. Print scope pill.
   Primary issue lookup is UNSCOPED (same convention as /bigeye-rca).

2. Resolve issue_ref → internal_id.
   - With --internal-id: arg is internal_id.
   - No arg: state.json.last_issue or prompt the user.
   - Otherwise: MCP search_issues. MCP unreachable → hard-fail with workaround
     "retry with --internal-id".

3. Verify snow profile.
   - profile = arg --snow OR profiles.json[active].snow.profile
   - Missing → "No Snowflake profile configured. Run /bigeye-config snow set <profile>."
   - `snow connection test -c <profile>` returns 0. Failed → print stderr +
     "Fix: Check ~/.snowflake/config.toml" and stop.

4. Build InvestigationRequest (request_id is a fresh uuid).

5. Print one-line intent:
     "Investigating I-{display_name} (pack: {pack_or_'auto'}, budget: {n},
      snow: {profile}). Typically takes 1-3 min. Streaming progress below."

6. Spawn subagent `bigeye-investigator` with InvestigationRequest as input.
   Subagent runs the engine, streams per-phase + per-query lines, returns
   InvestigationResult.

7. Validate result schema. On schema-invalid → save raw to
   investigations/<id>-<ts>.raw.txt; print error + raw path.

8. Render via Renderer adapter:
   - memo_md from references/memo-template.md + result.diagnosis + trace
   - ticket_body_md from references/memo-template.md ticket section

9. Persist:
   - investigations/<issue_id>-<iso8601>.json (full result, durable)
   - state.json updates: last_issue, last_table, last_investigation, append
     action to state.issues[<id>].actions
   - pruning per preamble Step 8.C

10. Emit final block:
      {memo_md}

      ---

      ### Copy-paste ticket body
      ```markdown
      {ticket_body_md}
      ```

      Trace saved: ~/.claude/bigeye-plugin/investigations/{file}
      Next: /bigeye-roster | /bigeye-ticket {display_name}
            /bigeye-investigate {display_name} --budget {n+5} (re-run wider)
```

## 6. `bigeye-investigator` subagent

`agents/bigeye-investigator/AGENT.md`. Receives the `InvestigationRequest` as input, runs the engine procedure, returns one JSON object matching `InvestigationResult`.

### 6.1 Tool allowlist

**Allowed:**
- `Bash` (for `snow sql -c <profile> --format json -q <sql>` and `bigeye` CLI fallbacks)
- BigEye MCP read tools: `get_issue`, `list_related_issues`, `get_table_profile`, `get_lineage_node`, `get_upstream_root_causes`, `list_table_issues`, `list_entity_tags`
- `Read` (pack files under `~/.claude/bigeye-plugin/packs/`)
- `Grep`

**BigEye access priority — MCP first, CLI fallback per call:** Each BigEye intake step (Phase 1.1–1.7) tries the MCP tool first. If a specific MCP call fails or is unavailable for that call, the adapter falls back to the equivalent `bigeye` CLI command (see existing pattern in `/bigeye-rca` Step 3: `bigeye -w <profile> issues get-issues -iid <internal_id>`). If MCP is unreachable at the very start of the run (engine cannot even resolve the issue), main thread hard-fails per §10 before dispatch. Mid-run MCP failures degrade gracefully via CLI; mid-run total BigEye outage falls into `IntakeFailedEvent` per §10.

**Denied:**
- `Write`, `Edit`, `NotebookEdit`
- BigEye MCP write tools (`update_issue`, `create_*`, `delete_*`, `tag_entity`, `untag_entity`)
- Any MCP / Bash that touches Jira / Asana / Slack

### 6.2 Subagent prompt skeleton

```
You are the BigEye investigator. You receive ONE InvestigationRequest
and return ONE InvestigationResult JSON object. Nothing else.

Follow skills/bigeye-investigate/references/engine.md exactly. Refer to
references/contracts.md for input/output schemas, references/adapters.md
for how to call BigEye + Snowflake, references/readonly-guard.md for the
SQL guard you MUST apply before every `snow sql` call.

Rules:
- Read-only. Reject any non-SELECT via the guard. Do NOT execute it.
- Respect budget. Each `snow sql` call (including widening COUNT pre-checks)
  consumes one budget unit.
- Mirror monitor WHERE clauses by default. Widening requires the COUNT
  pre-check from engine.md Phase 3.
- Stream a one-line trace summary to stdout before each query so the user
  sees progress.
- Return value is a single fenced JSON block matching InvestigationResult.
  Anything outside the JSON block is ignored.

If a step fails irrecoverably (Snowflake auth, BigEye unreachable, malformed
pack), return InvestigationResult with diagnosis.confidence=low,
diagnosis.reasoning describing the failure, and trace ending in
ErrorEvent { reason, recoverable: false }. Do NOT crash silently.
```

### 6.3 Streaming progress

Subagent prints one line per phase and one line per query before executing. Example:

```
[intake] fetched issue I-10921 — volume monitor on SOV.amazon_organic_rankings
[pack] resolved pack=sov via tag `sov` (2 candidates, priority 50 wins)
[hypothesis] ranked 6 hypotheses; top-3: amazon-category-restructure (prior=high),
              scraper-rate-limit (prior=medium), competitor-entry (prior=medium)
[query 1/10] amazon-category-restructure :: SELECT category_id, COUNT(*) ...
   → 12 categories returned, top has 0 rows in last 7 days
[query 2/10] amazon-category-restructure :: corroborator (widened, COUNT first)
   → COUNT: 8.2M rows, under threshold. Running widened query.
[query 3/10] amazon-category-restructure :: widened
   → 1 category dropped to zero; 11 stable
[diagnose] high confidence — amazon-category-restructure
   evidence: 2 confirming queries, no contradictions, scraper-rate-limit ruled out
[render] memo ready, returning
```

## 7. `/bigeye-pack` skill

Interactive scaffolder.

### 7.1 Subcommands

| Invocation | Behavior |
|---|---|
| `new <name>` | Walk the user through creating a new pack, write files, run lint |
| `lint <name>` | Validate an existing pack |
| `list` | List installed packs with tags + priorities + status |
| (no arg) | Show usage |

### 7.2 `new <name>` walk

1. Validate name (lowercase kebab-case, not `_default`). Stop if `~/.claude/bigeye-plugin/packs/<name>/` exists.
2. Ask description (one sentence).
3. Ask BigEye tags to match. Multi-select from existing workspace tags via MCP `list_tags`; user can also enter custom. At least one required.
4. Ask priority — multiple-choice 0 / 25 / 50 (recommended) / 75.
5. Ask sample table (`<schema>.<table>`). Verify via MCP `search_metadata`. Accept anyway if not found.
6. Ask issue types to cover (multi-select; default freshness + volume + null).
7. For each selected issue type, ask the user to describe one common failure pattern in one line. Skipping uses the `_default` hypothesis as starter.
8. Write `pack.yaml` + `hypotheses/<type>.md` (one stub per user line, plus one copied from `_default`) + `verification.md` template.
9. Run lint. Report warnings.
10. Print next steps (open files, fill TODO markers, test with `/bigeye-investigate <id> --pack <name>`, tag tables in BigEye when ready).

### 7.3 Lint checks

| Check | Severity | Rule |
|---|---|---|
| `pack.yaml` exists | error | required |
| `name` matches dir name | error | required |
| `tags` non-empty | error | required |
| `priority` in 0..100 | warn | recommend standard tiers |
| `covers` non-empty | error | required |
| Each `covers[i]` has `hypotheses/<i>.md` | error | required |
| Each hypothesis has all required fields | error | id/label/rationale/prior/expected_signal/query_template |
| `id` slug is unique within a file | error | duplicates ambiguous |
| `query_template` contains `{{monitor_where}}` OR `requires_widening: true` | error | otherwise filter mirroring silently bypassed |
| Hypothesis count per file ≥ 2 | warn | one-hypothesis files give engine nothing to rule out |
| `verification.md` present if any `playbook_link` mentions "Manual verification" | warn | trigger declared without steps |
| TODO markers remaining | warn | "<n> stubs not filled in" |

## 8. Existing-skill changes

### 8.1 `/bigeye-roster` — add `[v]` investigate

Edit `skills/bigeye/references/roster.md`.

**New action menu:** `[i]mprove [v]investigate [c]lose [f]laky-note [t]icket [h]int [s]kip`

**Recommendation derivation** (which action roster suggests):

| Condition | Recommendation |
|---|---|
| Issue type ∈ {freshness, volume, null, distribution, schema, custom} AND age < 24h AND no prior `bigeye-investigate` action on this issue | `v` |
| Same type, prior `bigeye-investigate` exists with confidence ∈ {high, medium} | `t` (ticket — already diagnosed) |
| Issue is metric-config / threshold-tuning shape (recent monitor change, flapping) | `i` (unchanged) |
| Suppressible noise (flaky pattern, expected gap) | `f` (unchanged) |

**`[v]` handler:**

```
1. Confirm: "Investigate I-{id}? snow={profile}, pack={resolved}, budget=10. (y/n)"
   If pack resolves to `_default`, add: "No domain pack matched tags. Using
   default. Investigate anyway? (y/n)"
2. On y: hand off to /bigeye-investigate <id>. Roster pauses until the sub-skill
   returns. On return, append { skill: "bigeye-roster", action: "investigate",
   at, confidence } to state.json.issues[<id>].actions. Print resume marker.
3. On n: same as `s` (skip).
```

End-of-pass summary picks up the new counter (`investigate: v`).

### 8.2 `/bigeye-config` — add `snow ...` subcommands

Schema addition to `profiles.json` per profile:

```json
{
  "snow": {
    "profile": "ro-analytics",
    "default_warehouse": "ANALYTICS_RO_WH",
    "default_role": "DATA_READER"
  }
}
```

**Subcommands:**

| Invocation | Behavior |
|---|---|
| `snow show` | Print active profile's `snow` block + which `~/.snowflake/config.toml` connection it maps to |
| `snow set <profile>` | Set `snow.profile` on active profile. Verify connection exists. Run `snow connection test -c <profile>` |
| `snow set <profile> --warehouse <w>` | Same + set `default_warehouse` |
| `snow set <profile> --role <r>` | Same + set `default_role` |
| `snow unset` | Remove `snow` block from active profile |
| `snow verify` | Run `snow connection test` + run a canary `SELECT 1` + parse `SHOW GRANTS` for write privileges. Print PASS/FAIL per check |

`snow verify` warns (does not fail) if the role has any of `INSERT|UPDATE|DELETE|TRUNCATE|CREATE|DROP|ALTER|MERGE|GRANT|REVOKE` grants. Includes a copy-paste role-setup block for ACCOUNTADMIN to run once.

Existing `/bigeye-config verify` four-point check extends to five points:

```
1. CLI install         ✓ bigeye 0.x.x
2. CLI workspace       ✓ prod
3. CLI auth            ✓
4. MCP reachability    ✓ bigeye
5. Snowflake           ✓ snow profile=ro-analytics, role=DATA_READER (read-only ✓)
```

### 8.3 `state.json` — add `last_investigation`

```json
{
  "last_workflow": "bigeye-investigate",
  "last_issue": "10921",
  "last_table": "SOV.amazon_organic_rankings",
  "last_investigation": {
    "issue": "10921",
    "request_id": "01HX...",
    "at": "2026-05-12T15:42:00Z",
    "confidence": "high",
    "pack_used": "sov",
    "diagnosis_id": "amazon-category-restructure",
    "trace_path": "investigations/10921-2026-05-12T15-42-00Z.json"
  }
}
```

Used by `(no arg)` resume on `/bigeye-investigate`.

## 9. Read-only guard

`references/readonly-guard.md`. Two layers.

### 9.1 Layer 1 — engine-side SQL validation

Wraps every `SnowClient.execute()` call. Subagent rejects writes before invoking `snow sql`.

```python
def assert_readonly(sql: str) -> None:
    # 1. Normalize
    s = strip_block_comments(sql)       # /* ... */
    s = strip_line_comments(s)          # -- ... \n
    s = re.sub(r"\s+", " ", s).strip().lower()

    # 2. Reject empty
    if not s:
        raise GuardError("empty query")

    # 3. First token must be SELECT or WITH
    first = s.split(" ", 1)[0]
    if first not in {"select", "with"}:
        raise GuardError(f"first token {first!r}; expected select|with")

    # 4. Denylist scan (whole-word, including after `;`)
    DENY = (
        "insert","update","delete","merge","create","drop","alter",
        "truncate","grant","revoke","copy","put","get","use","call",
        "execute","unload","stream","task","procedure",
    )
    for kw in DENY:
        if re.search(rf"(^|;|\s){kw}\b", s):
            raise GuardError(f"forbidden keyword {kw!r}")

    # 5. Reject SELECT ... INTO
    if re.search(r"\binto\b", s):
        raise GuardError("'into' clause not allowed")

    # 6. At most one statement
    stmts = [x for x in s.rstrip(";").split(";") if x.strip()]
    if len(stmts) > 1:
        raise GuardError(f"{len(stmts)} statements found; only one SELECT allowed")
```

On `GuardError`: do NOT call `snow sql`. Append `GuardRejectEvent { sql, reason }` to trace. Budget NOT consumed. Continue with next hypothesis. If 3 guard rejects accumulate in a row, abort the engine loop with confidence=low + `EngineAbortEvent`.

### 9.2 Layer 2 — Snowflake-side read-only role

Operational, not enforced by the plugin. `/bigeye-config snow verify` checks and warns. The plugin documents the recommended role:

```sql
CREATE ROLE DATA_READER;
GRANT USAGE ON WAREHOUSE <wh>      TO ROLE DATA_READER;
GRANT USAGE ON DATABASE <db>       TO ROLE DATA_READER;
GRANT USAGE ON ALL SCHEMAS IN ...  TO ROLE DATA_READER;
GRANT SELECT ON ALL TABLES IN ...  TO ROLE DATA_READER;
GRANT ROLE DATA_READER             TO USER <you>;
```

## 10. Error taxonomy

Each error class uses the existing Error/Fix/Why block convention from `preamble.md` Step 7.

| Class | Where | Behavior |
|---|---|---|
| BigEye MCP unreachable at start | main thread, pre-dispatch | reconnect block per preamble 7.E, stop |
| BigEye intake fails after retry | subagent Phase 1 | return InvestigationResult with confidence=low + `IntakeFailedEvent` |
| Display-name unresolved | main thread | "BigEye returned no match for issue '<n>'." with fix line |
| Snowflake profile missing | main thread, pre-dispatch | "No Snowflake profile configured. Run /bigeye-config snow set <profile>." |
| `snow connection test` fails | main thread, pre-dispatch | print stderr + "Fix: Check ~/.snowflake/config.toml" |
| `snow sql` returns non-zero | subagent mid-loop | parse stderr; append `SnowflakeErrorEvent`; mark hypothesis untested; continue. 3 consecutive auth errors → abort |
| Pack file malformed | subagent Phase 2 | append `PackErrorEvent`; fall through to `_default` with trace note |
| Pack tag matches multiple | subagent Phase 2 | resolve by priority; append `PackResolveEvent` listing candidates |
| Budget exhausted | subagent Phase 3 | break loop; confidence=low; memo includes `--budget <n+5>` next step |
| Guard rejects 3+ in a row | subagent | `EngineAbortEvent`, return with confidence=low |
| Subagent timeout (no return in 5 min) | main thread | "Investigator timed out. Partial trace at <path>." Save partial as `.partial.json` |
| Subagent invalid schema | main thread | save raw as `.raw.txt`; do NOT update `state.last_investigation` |
| User Ctrl-C | main thread | kill subagent; save partial trace if any; do not update state |

### 10.1 Hard refusals (spec §6)

| Request | Refusal |
|---|---|
| Modify BigEye issue inside an investigation | "Refused. /bigeye-investigate is read-only on BigEye. Use /bigeye-roster action [c]lose or /bigeye-incidents close." |
| Create Jira/Asana ticket inside an investigation | "Refused. Investigator only generates the ticket body. Paste it yourself, or use /bigeye-ticket <id>." |
| Run a non-SELECT query | "Refused. Investigator is read-only on Snowflake. Specifically: <guard reason>." |
| Bypass budget mid-investigation | "Refused. Budget is set at start. Re-run with --budget <n>." |
| Bypass read-only restriction | "Refused. Read-only is a hard rule (NFR-1). No override." |

**Deviation from spec FR-1.3:** spec said reject non-SOV tables with a clear message. Removed — the agent is generic. Replaced with a soft `_default`-pack confirmation: `"No domain pack matched tags <list>. Using _default. Continue? (y/n)"`. User can confirm or abort.

### 10.2 State write rules

| Outcome | `last_investigation` updated? | trace file written? |
|---|---|---|
| Confidence high | yes | yes |
| Confidence medium | yes | yes |
| Confidence low (clean finish) | yes | yes |
| Manual-verification switch | yes | yes |
| Budget exhausted | yes (confidence=low) | yes |
| Engine abort (guard rejects) | yes (confidence=low) | yes |
| Subagent timeout | no | yes (`.partial.json`) |
| Subagent invalid return | no | yes (`.raw.txt`) |
| User Ctrl-C | no | partial if emitted; otherwise no |
| Snow profile missing / unreachable at start | no | no |

Rule: any time the engine ran at least one phase, write a trace file. Only update `last_investigation` when the result is structured and resumable.

## 11. Testing

### 11.1 Layer 1 — engine unit tests (`tests/bigeye_investigate/engine/`)

Pure-function tests over `engine.md` algorithm with fake adapters.

- intake resolves display name via correct client call
- pack resolve: priority tiebreak, multiple matches, no match → `_default`
- hypothesis ranking uses prior + LLM heuristic
- filter mirroring on by default; `{{monitor_where}}` substituted
- widening requires COUNT first; budget consumed
- widening above threshold → `SkippedEvent`, main query not run
- evidence-count rubric: high / medium / low boundary conditions
- budget exhaustion returns confidence=low + populated `untested_alternatives`
- manual-verification switch triggers and populates `manual_steps`
- corroborator never runs on contradicted hypothesis

### 11.2 Layer 2 — guard tests (`tests/bigeye_investigate/readonly_guard/`)

Black-box: feed string, expect pass or specific `GuardError`. Coverage groups:

- pass: `SELECT 1`, lower/upper/mixed case, comments, WITH cte, trailing semicolon
- reject denylist: every keyword in `DENY`
- reject multi-statement: `SELECT 1; DROP TABLE t`
- reject sneaky: comment-hidden write, `SELECT ... INTO`, leading whitespace + UPDATE, no-space `SELECT;DROP`
- reject first-token: `EXPLAIN`, `DESC`, `SHOW`
- edge: empty, whitespace-only, comment-only with `drop` inside

### 11.3 Layer 3 — end-to-end replay (`tests/bigeye_investigate/e2e/`)

Replay harness wires `BigeyeClient` and `SnowClient` to fixture dirs:

```
case-volume-amazon/
  request.json
  bigeye_responses/
  snow_responses/             # one JSON per query SQL hash
  pack/
  expected_diagnosis.json
  expected_trace_events.json
  expected_memo.snap.md
```

Five fixtures cover freshness, volume, null, distribution, custom. Schema stays manual smoke (structural, not statistical).

### 11.4 Layer 4 — live smoke (manual, per release)

Three real BigEye issues per release. Run `/bigeye-investigate <id>`. Verify:

- Memo renders and ticket body is paste-ready.
- Trace file written under `investigations/`.
- Snowflake query history shows `role=DATA_READER`.
- `INFORMATION_SCHEMA.ACCESS_HISTORY` shows only SELECTs in the run window.

### 11.5 Spec SC-1 accuracy — deferred to v1.1

Spec SC-1 requires ≥70% root-cause match on 20 historical SOV issues. v1 does not measure this — the replay harness over the `investigations/` archive lands in v1.1 once we have enough recorded runs.

## 12. Rollout plan

Phased, each phase gated on the previous being stable.

**Phase 0 — Scaffolding.** Engine pseudocode, adapter contracts, read-only guard, `_default` pack with stub hypotheses (labels only, no SQL). Unit tests for engine + guard. No skill wired up. Plugin → 0.6.0-alpha.

**Phase 1 — `/bigeye-investigate` happy path.** Skill + subagent. `/bigeye-config snow` subcommands. `_default` pack hypotheses get real SQL. E2E replay tests pass on all 5 fixtures. Live smoke on 3 issues. Plugin → 0.6.0.

**Phase 2 — Pack surface.** `/bigeye-pack new` + `lint` + `list`. SOV pack lands externally (user-side, not in plugin repo). Roster `[v]` action wired in. Plugin → 0.6.1.

**Phase 3 — Parallel multi-issue (v1.1).** `/bigeye-investigate <id1> <id2> <id3>` fans out via parallel subagents. Cross-investigation related-root check. SC-1 evaluation harness. Plugin → 0.7.0.

## 13. Deferred to v1.1+

| Deferred | v1 behavior | When unblocked |
|---|---|---|
| Multi-issue (2-3 IDs in parallel) | accepts only one ID; prints "v1 single-issue, v1.1 parallel" if user passes more | v1.1, Phase 3 |
| Auto-trigger from BigEye webhook | not exposed; engine is webhook-ready via adapter seam | server extraction (v2) |
| Slack delivery of memo | renderer adapter pluggable; v1 chat-only | v2 |
| Jira / Asana API ticket creation | ticket body remains copy-paste markdown | v2 |
| Live retailer browsing (Chrome) | manual verification steps printed only | v2 or never |
| Resolution actions (BigEye writes, data fixes) | hard-refused | out of scope permanently |
| Multi-warehouse (BigQuery, Postgres) | Snowflake-only; adapter seam ready | v1.2 if demand |
| Pack version migration | no `version_migrate` in pack.yaml | once a breaking pack-format change exists |
| Auto-generate pack queries from history | `/bigeye-pack new` creates stubs with TODO markers | v1.2 |
| Confidence calibration tuning | evidence-count rubric fixed for v1 | after SC-1 measurement |
| `/bigeye-investigate explain <id>` (post-hoc render of a stored result) | trace files are durable, purely a renderer | v1.1 cheap |

## 14. Success-criteria mapping

| Spec | Design realization |
|---|---|
| **SC-1** ≥70% root-cause match on 20 historical | Deferred to v1.1 measurement via replay over `investigations/` archive |
| **SC-2** median ≤3 min wall-clock | Met by subagent dispatch + 10-query budget + per-query `snow sql` timeout (60s default) |
| **SC-3** ticket body needs no structural editing | `memo-template.md` produces ready-to-paste markdown; reviewed against actual Jira and Asana paste targets in Phase 1 live smoke |
| **SC-4** zero writes against Snowflake | Two-layer guard: engine-side regex + role-side grants. `INFORMATION_SCHEMA.ACCESS_HISTORY` confirms in live smoke |

## 15. Non-functional mapping

| Spec NFR | Design |
|---|---|
| **NFR-1** read-only | guard layer 1 + layer 2 |
| **NFR-2** ≤3 min, stream progress | subagent prints one line per phase + per query |
| **NFR-3** reproducible trace | `investigations/<id>-<ts>.json` per run |
| **NFR-4** confidence required | engine Phase 4 always sets confidence; memo template requires it |
| **NFR-5** trigger phrases | skill description includes "investigate", "diagnose", "what's wrong with table"; URL parse handled by Phase 1.1 |
| **NFR-6** markdown edits, no code | packs + verification + memo template all markdown |

## 16. Open questions resolved in this design

Tracking against `docs/spec.md` §8:

| Spec Q | Resolution |
|---|---|
| Which Snowflake user/role does the agent connect as? | User-configured `snow.profile` per BigEye profile. `/bigeye-config snow verify` warns if the role has write grants. Recommended: dedicated `DATA_READER`. |
| Where do playbooks live? | `~/.claude/bigeye-plugin/packs/<name>/` (external dir, per-user). `_default` ships in plugin repo. |
| Confidence rubric | Evidence-count rubric. High = 1 confirmed + ≥2 corroborating + 0 contradicting + alternatives ruled out. |
| Investigation budget | 10 queries, fixed per spec default. Pack-overridable via `pack.yaml.budget`. Per-invocation override via `--budget <n>`. |
| Multi-issue mode | v1 = 1 ID. v1.1 = up to 3 in parallel via subagents. |

## 17. Deviations from spec (recorded for audit)

| Spec | Deviation | Rationale |
|---|---|---|
| §3.3, §5: Snowflake MCP | `snow` CLI instead | Read-only role enforcement is operational (Snowflake side); `snow connection test` gives a deterministic auth check; MCP server is not currently the read path for Snowflake in this plugin |
| §2 Scope: SOV tables only | Generic across all BigEye users; SOV becomes one pack | "Java interface + impls" architecture user requested; broader reuse without sacrificing SOV depth |
| §3.1 FR-1.3: reject non-SOV tables | Soft `_default`-pack confirmation instead of hard refusal | Generic architecture; user can opt out per-investigation |
| §5: Ticket templates in skill | Templates live in pack `playbook_link` blocks + central `memo-template.md` | Domain-specific ticket framing belongs with the pack; structural template stays central |
