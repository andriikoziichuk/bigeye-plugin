# BigEye DQ Investigator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/bigeye-investigate <issue>`: a read-only Snowflake-backed investigation agent that diagnoses BigEye data quality issues and returns a confidence-rated resolution memo, plus the pluggable pack format and `/bigeye-pack` scaffolder it depends on.

**Architecture:** Investigation engine lives as portable pseudocode in `skills/bigeye-investigate/references/engine.md`. `/bigeye-investigate` dispatches the `bigeye-investigator` subagent which runs the loop in isolation, returning a structured `InvestigationResult`. Adapters (BigeyeClient / SnowClient / PackLoader / Renderer) are documented contracts the skill wires to Claude Code tools today and a future Python service wires to native libraries tomorrow. Read-only guard is a Python script for deterministic safety. Packs (failure-pattern knowledge per BigEye-tagged domain) live under `~/.claude/bigeye-plugin/packs/<name>/`.

**Tech Stack:** Claude Code skills (markdown), Python ≥3.9 (helpers + tests), BigEye MCP server, BigEye CLI fallback, Snowflake `snow` CLI, pytest for unit tests, fixture JSON for replay tests, manual `scenarios.md` for live smoke.

**Scope:** v1 covers design §12 Phases 0 + 1 + 2. Phase 3 (parallel multi-issue, `/bigeye-investigate <id1> <id2> <id3>`) is v1.1 and out of scope for this plan.

**Design reference:** `docs/superpowers/specs/2026-05-12-bigeye-dq-investigator-design.md`.

---

## File Structure

**New files (plugin repo):**

```
tools/                                           # NEW dir; deterministic helpers invoked via Bash
  __init__.py
  readonly_guard.py                              # SQL guard CLI: python -m tools.readonly_guard <sql>
  pack_lint.py                                   # python -m tools.pack_lint <pack_dir>
  pack_render.py                                 # python -m tools.pack_render --template <f> --vars <json>

skills/bigeye-investigate/
  SKILL.md                                       # main-thread orchestrator
  references/
    engine.md                                    # portable pseudocode
    contracts.md                                 # InvestigationRequest / Result schemas
    adapters.md                                  # BigeyeClient / SnowClient / PackLoader / Renderer contracts
    memo-template.md                             # memo + ticket-body markdown templates
    readonly-guard.md                            # guard contract + how to invoke tools/readonly_guard.py
  _default_pack/
    pack.yaml
    hypotheses/freshness.md
    hypotheses/volume.md
    hypotheses/null.md
    hypotheses/distribution.md
    hypotheses/schema.md
    hypotheses/custom.md
    verification.md

skills/bigeye-pack/
  SKILL.md                                       # /bigeye-pack new / lint / list
  templates/
    pack.yaml.tmpl
    hypothesis.md.tmpl
    verification.md.tmpl

agents/bigeye-investigator/
  AGENT.md                                       # subagent prompt + tool allowlist

tests/
  test_readonly_guard.py
  test_pack_lint.py
  test_pack_render.py
  test_engine_replay.py
  fixtures/
    readonly_guard_cases.json
    pack_lint_cases/                             # one subdir per case
      good_minimal/...
      bad_missing_tags/...
      bad_unique_id/...
      bad_filter_mirroring/...
    engine_replay/                               # one subdir per case
      case-freshness-default/
        request.json
        bigeye_responses/...
        snow_responses/...
        pack/...
        expected_diagnosis.json
        expected_trace_events.json
      case-volume-amazon/...
      case-null-default/...
      case-distribution-default/...
      case-custom-default/...
  scenarios.md                                   # MODIFY: append investigator scenarios
```

**Files modified (plugin repo):**

```
skills/bigeye-config/SKILL.md                    # add `snow ...` subcommand surface
skills/bigeye/references/preamble.md             # add 5th verify point (snow profile)
skills/bigeye/references/roster.md               # add [v]investigate action
README.md                                        # add /bigeye-investigate + /bigeye-pack to commands table
pyproject.toml                                   # bump version to 0.6.0
```

**Files modified (per-user, NOT in repo, documented only):**

```
~/.claude/bigeye-plugin/profiles.json            # add `snow: { profile, default_warehouse, default_role }`
~/.claude/bigeye-plugin/state.json               # add `last_investigation`
~/.claude/bigeye-plugin/packs/_default/...       # copied from plugin _default_pack/ on first run
~/.claude/bigeye-plugin/investigations/          # per-run trace archive (created on first investigation)
```

---

# PHASE 0 — Scaffolding

Goal: contracts, guard, engine pseudocode, default pack with stub hypotheses, all tests for the deterministic parts. No skill wired up yet. Outputs are read-only artifacts that the LLM-driven loop will follow in Phase 1.

## Task 1: Contracts reference doc

**Files:**
- Create: `skills/bigeye-investigate/references/contracts.md`

- [ ] **Step 1: Create the contracts doc**

Write `skills/bigeye-investigate/references/contracts.md` with the schemas. Use markdown code blocks; the engine and adapters refer to these by name.

````markdown
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

## InvestigationResult

```jsonc
{
  "request": { /* InvestigationRequest verbatim */ },
  "issue_snapshot": {
    "internal_id": 42,
    "display_name": "10921",
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
    "tags_source": []
  },
  "pack_used": "sov",
  "trace": [ /* list of TraceEvent — see TraceEvent below */ ],
  "diagnosis": {
    "hypothesis_id": "amazon-category-restructure",
    "confidence": "high",                      // high | medium | low
    "reasoning_md": "markdown explaining the call",
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
  "sql": "SELECT ...", "row_count": 12, "ms": 1820,
  "result_summary": "12 categories, top has 0 rows in last 7 days",
  "rows_sample": [ { "category_id": "...", "rows": 0 } ]   // ≤ 50 rows
}

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
````

- [ ] **Step 2: Commit**

```bash
git add skills/bigeye-investigate/references/contracts.md
git commit -m "feat(investigate): add InvestigationRequest/Result/TraceEvent contracts"
```

---

## Task 2: Adapters reference doc

**Files:**
- Create: `skills/bigeye-investigate/references/adapters.md`

- [ ] **Step 1: Create the adapters doc**

````markdown
# Adapter Contracts

The engine calls four adapters. v1 implementations are the skill's tool bindings; a future Python service implements native versions of the same interfaces.

## BigeyeClient

```
resolve(issue_ref: str, internal_id_flag: bool) -> { internal_id: int, display_name: str }
get_issue(internal_id: int) -> IssueDetails
get_metric_history(internal_id: int, window: int = 30) -> list[Run]
get_table_profile(table_fq: str) -> TableProfile
get_lineage(table_fq: str, max_depth: int = 5) -> LineageGraph
get_upstream_issues(table_fq: str) -> list[IssueRef]
get_related_issues(internal_id: int, days: int = 30) -> list[IssueRef]
get_tags(entity_id: int, entity_kind: "table"|"source") -> list[str]
```

**v1 binding rules — MCP first, CLI fallback per call:**

| Method | MCP tool | CLI fallback |
|---|---|---|
| `resolve` (display→internal) | `mcp__bigeye__search_issues` | none (hard-fail if MCP down at start) |
| `get_issue` | `mcp__bigeye__get_issue` | `bigeye -w <p> issues get-issues -iid <id> -op <tmp>` |
| `get_metric_history` | `mcp__bigeye__get_issue` (events array) | same as above |
| `get_table_profile` | `mcp__bigeye__get_table_profile` | `bigeye -w <p> catalog profile -t <fq>` |
| `get_lineage` | `mcp__bigeye__get_lineage_graph` | (no fallback; degrade) |
| `get_upstream_issues` | `mcp__bigeye__list_report_upstream_issues` | (no fallback; degrade) |
| `get_related_issues` | `mcp__bigeye__list_related_issues` | (no fallback; degrade) |
| `get_tags` | `mcp__bigeye__list_entity_tags` | (no fallback; degrade) |

If MCP fails on one call and no CLI fallback exists, the adapter returns an empty result and appends a `pack_error`-style trace note ("BigEye <method> unavailable; degraded").

## SnowClient

```
test_connection(profile: str) -> { ok: bool, stderr: str? }
execute(sql: str, profile: str, timeout_s: int = 60) -> { rows: list, row_count: int, ms: int, stderr: str? }
```

**v1 binding:**
- Every `execute()` MUST first call `python -m tools.readonly_guard "<sql>"`. Non-zero exit → raise `GuardError(stderr)`. Engine appends `guard_reject` trace event and does NOT call Snowflake.
- Otherwise: `snow sql -c <profile> --format json -q <sql>` via Bash with a 60s timeout. Parse JSON to `{rows, row_count}`.
- Limit returned `rows` to first 50 (`rows_sample` field of `QueryEvent`).

## PackLoader

```
list_packs() -> list[PackMeta]
load_pack(name: str) -> Pack
resolve_pack_for_tags(tags: list[str], override: str?) -> Pack    # returns _default on no match
```

**v1 binding:** filesystem read of `~/.claude/bigeye-plugin/packs/*/`. On first run, if `~/.claude/bigeye-plugin/packs/_default/` is absent, copy from `skills/bigeye-investigate/_default_pack/`.

## Renderer

```
render_memo(result: InvestigationResult) -> str       # markdown
render_ticket_body(result: InvestigationResult) -> str # markdown subset
```

**v1 binding:** read `references/memo-template.md`, substitute placeholders from `result`. Emits to Claude Code chat (main-thread skill).

**v2 binding (future):** Slack blocks, Jira REST payload, etc. Same input shape; different output format.
````

- [ ] **Step 2: Commit**

```bash
git add skills/bigeye-investigate/references/adapters.md
git commit -m "feat(investigate): add BigeyeClient/SnowClient/PackLoader/Renderer contracts"
```

---

## Task 3: Read-only guard — failing tests first

**Files:**
- Create: `tests/fixtures/readonly_guard_cases.json`
- Create: `tests/test_readonly_guard.py`

- [ ] **Step 1: Write the test fixture**

Create `tests/fixtures/readonly_guard_cases.json` with all coverage groups from design §11.2:

```json
[
  { "sql": "SELECT 1", "ok": true },
  { "sql": "select * from t", "ok": true },
  { "sql": "WITH cte AS (SELECT 1) SELECT * FROM cte", "ok": true },
  { "sql": "select a, b /* comment */ from t where c = 1", "ok": true },
  { "sql": "select * from t limit 100;", "ok": true },
  { "sql": "  \n\tselect 1\n", "ok": true },
  { "sql": "SeLeCt 1 FrOm T", "ok": true },
  { "sql": "select * from t -- trailing\n", "ok": true },

  { "sql": "INSERT INTO t VALUES (1)", "ok": false, "reason_contains": "insert" },
  { "sql": "update t set a=1", "ok": false, "reason_contains": "update" },
  { "sql": "DELETE FROM t", "ok": false, "reason_contains": "delete" },
  { "sql": "DROP TABLE t", "ok": false, "reason_contains": "drop" },
  { "sql": "ALTER TABLE t ADD COLUMN x INT", "ok": false, "reason_contains": "alter" },
  { "sql": "MERGE INTO t USING s ON 1=1", "ok": false, "reason_contains": "merge" },
  { "sql": "truncate t", "ok": false, "reason_contains": "truncate" },
  { "sql": "grant select on t to role r", "ok": false, "reason_contains": "grant" },
  { "sql": "REVOKE select on t from role r", "ok": false, "reason_contains": "revoke" },
  { "sql": "COPY INTO @stage FROM t", "ok": false, "reason_contains": "copy" },
  { "sql": "PUT file://a.csv @stage", "ok": false, "reason_contains": "put" },
  { "sql": "GET @stage file://", "ok": false, "reason_contains": "get" },
  { "sql": "use database d", "ok": false, "reason_contains": "use" },
  { "sql": "call my_proc()", "ok": false, "reason_contains": "call" },
  { "sql": "EXECUTE IMMEDIATE 'SELECT 1'", "ok": false, "reason_contains": "execute" },

  { "sql": "SELECT 1; DROP TABLE t", "ok": false, "reason_contains": "statements" },
  { "sql": "SELECT 1; SELECT 2", "ok": false, "reason_contains": "statements" },
  { "sql": "SELECT;DROP TABLE t", "ok": false, "reason_contains": "drop" },

  { "sql": "SELECT * FROM t /* ; drop table t */", "ok": true },
  { "sql": "select * into new_t from t", "ok": false, "reason_contains": "into" },
  { "sql": "select * from t ; -- nothing\n drop table t", "ok": false, "reason_contains": "drop" },
  { "sql": "\nUPDATE t\n SET a=1", "ok": false, "reason_contains": "update" },
  { "sql": "SeLeCt * iNtO new FROM t", "ok": false, "reason_contains": "into" },

  { "sql": "EXPLAIN SELECT 1", "ok": false, "reason_contains": "first token" },
  { "sql": "DESC TABLE t", "ok": false, "reason_contains": "first token" },
  { "sql": "SHOW TABLES", "ok": false, "reason_contains": "first token" },

  { "sql": "", "ok": false, "reason_contains": "empty" },
  { "sql": "   \n\t  ", "ok": false, "reason_contains": "empty" },
  { "sql": "-- only comment with drop in it\n", "ok": false, "reason_contains": "empty" }
]
```

- [ ] **Step 2: Write the failing test runner**

Create `tests/test_readonly_guard.py`:

```python
"""Unit tests for tools.readonly_guard. Fixture-driven, no network."""
import json
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "readonly_guard_cases.json"
REPO = Path(__file__).resolve().parent.parent


def run_guard(sql: str) -> tuple[int, str]:
    """Invoke the CLI form the skill will use: `python -m tools.readonly_guard <sql>`."""
    proc = subprocess.run(
        [sys.executable, "-m", "tools.readonly_guard", sql],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return proc.returncode, (proc.stderr or "").lower()


def main() -> int:
    cases = json.loads(FIXTURE.read_text())
    failures = []
    for case in cases:
        sql = case["sql"]
        want_ok = case["ok"]
        rc, stderr = run_guard(sql)
        got_ok = rc == 0
        if got_ok != want_ok:
            failures.append((sql, want_ok, got_ok, stderr))
            continue
        if not want_ok:
            needle = case.get("reason_contains", "").lower()
            if needle and needle not in stderr:
                failures.append((sql, f"reason ~ {needle}", stderr, ""))
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print(f"OK — {len(cases)} guard cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run the test — expect failure (module doesn't exist)**

```bash
python tests/test_readonly_guard.py
```

Expected: every case fails because `tools.readonly_guard` doesn't exist yet (`No module named tools`).

- [ ] **Step 4: Create `tools/` package**

```bash
mkdir -p tools && touch tools/__init__.py
```

- [ ] **Step 5: Implement `tools/readonly_guard.py`**

Create `tools/readonly_guard.py`:

```python
"""Read-only SQL guard. CLI: `python -m tools.readonly_guard <sql>`.

Exit 0  → SQL is read-only and safe to execute.
Exit 1  → SQL rejected. Reason on stderr.
Exit 2  → Misuse (no arg).

Two-layer defense; this is layer 1 (engine-side). Layer 2 is the Snowflake
read-only role grant — see /bigeye-config snow verify.
"""

from __future__ import annotations

import re
import sys

DENY = (
    "insert", "update", "delete", "merge", "create", "drop", "alter",
    "truncate", "grant", "revoke", "copy", "put", "get", "use", "call",
    "execute", "unload", "stream", "task", "procedure",
)


class GuardError(Exception):
    pass


def _strip_block_comments(s: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", s, flags=re.DOTALL)


def _strip_line_comments(s: str) -> str:
    return re.sub(r"--[^\n]*", " ", s)


def assert_readonly(sql: str) -> None:
    if sql is None:
        raise GuardError("null sql")
    s = sql
    s = _strip_block_comments(s)
    s = _strip_line_comments(s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    if not s:
        raise GuardError("empty query")
    first = s.split(" ", 1)[0]
    if first not in {"select", "with"}:
        raise GuardError(f"first token {first!r}; expected select|with")
    for kw in DENY:
        if re.search(rf"(^|;|\s){kw}\b", s):
            raise GuardError(f"forbidden keyword {kw!r}")
    if re.search(r"\binto\b", s):
        raise GuardError("'into' clause not allowed")
    stmts = [x for x in s.rstrip(";").split(";") if x.strip()]
    if len(stmts) > 1:
        raise GuardError(f"{len(stmts)} statements found; only one SELECT allowed")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m tools.readonly_guard <sql>", file=sys.stderr)
        return 2
    sql = argv[1]
    try:
        assert_readonly(sql)
        return 0
    except GuardError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 6: Run the test — expect pass**

```bash
python tests/test_readonly_guard.py
```

Expected: `OK — 36 guard cases` (count matches fixture length).

- [ ] **Step 7: Commit**

```bash
git add tools/__init__.py tools/readonly_guard.py \
        tests/test_readonly_guard.py tests/fixtures/readonly_guard_cases.json
git commit -m "feat(investigate): add read-only SQL guard with fixture-driven tests"
```

---

## Task 4: Read-only guard reference doc

**Files:**
- Create: `skills/bigeye-investigate/references/readonly-guard.md`

- [ ] **Step 1: Write the doc**

````markdown
# Read-Only SQL Guard

Two-layer defense. Both must pass for any Snowflake call from the investigator.

## Layer 1 — engine-side (this guard)

Implemented in `tools/readonly_guard.py`. Invoked by the subagent before every `snow sql` call.

**CLI contract:**

```bash
python -m tools.readonly_guard "<sql>"
```

Exit codes:
- `0` — SQL is read-only and safe to execute.
- `1` — SQL rejected. Reason on stderr.
- `2` — misuse (no arg).

**Subagent behavior on rejection:**

1. Do NOT call `snow sql`.
2. Append `{ "kind": "guard_reject", "sql": "<sql>", "reason": "<stderr>" }` to trace.
3. Budget is NOT consumed.
4. Continue with the next hypothesis.
5. If three guard rejects accumulate in a row, abort the engine loop with `{ "kind": "engine_abort", "reason": "3 consecutive guard rejects" }` and return `diagnosis.confidence = "low"`.

**What the guard rejects:**

- Non-`SELECT`/`WITH` first token (e.g. `EXPLAIN`, `DESC`, `SHOW`).
- Any of: `insert`, `update`, `delete`, `merge`, `create`, `drop`, `alter`, `truncate`, `grant`, `revoke`, `copy`, `put`, `get`, `use`, `call`, `execute`, `unload`, `stream`, `task`, `procedure` (whole-word, including after a `;`).
- `SELECT ... INTO` (creates a table via implicit DDL on some warehouses).
- Multi-statement queries.
- Empty / whitespace-only / comment-only queries.

**What the guard does NOT do:**

- Does not parse SQL into an AST. It is a textual denylist.
- Does not check table/schema permissions — that is Layer 2's job.
- Does not check that the query is *meaningful* — only that it is structurally read-only.

## Layer 2 — Snowflake-side read-only role

Operational. The plugin documents (does not enforce) the recommended role. `/bigeye-config snow verify` warns if the connected role has write privileges.

```sql
CREATE ROLE DATA_READER;
GRANT USAGE ON WAREHOUSE <wh>      TO ROLE DATA_READER;
GRANT USAGE ON DATABASE <db>       TO ROLE DATA_READER;
GRANT USAGE ON ALL SCHEMAS IN ...  TO ROLE DATA_READER;
GRANT SELECT ON ALL TABLES IN ...  TO ROLE DATA_READER;
GRANT ROLE DATA_READER             TO USER <you>;
```

## Tests

See `tests/test_readonly_guard.py` + `tests/fixtures/readonly_guard_cases.json`. Run:

```bash
python tests/test_readonly_guard.py
```
````

- [ ] **Step 2: Commit**

```bash
git add skills/bigeye-investigate/references/readonly-guard.md
git commit -m "docs(investigate): add read-only guard reference"
```

---

## Task 5: Engine pseudocode

**Files:**
- Create: `skills/bigeye-investigate/references/engine.md`

- [ ] **Step 1: Write the engine doc**

Translate design §3.2 into the canonical procedure the subagent follows. Use plain pseudocode — no Claude-Code-specific keywords.

````markdown
# Investigation Engine — pseudocode

The engine is a procedure any runtime can follow. v1 runtime is the `bigeye-investigator` subagent; v2 runtime will be a Python service. Both wire to the adapters defined in `adapters.md`.

Inputs and outputs are defined in `contracts.md`.

## State per run

```
trace          : ordered list of TraceEvent
budget_used    : int (incremented per executed Snowflake query, INCLUDING widening COUNT pre-checks)
hypotheses     : list ranked by (prior_weight × fits_issue_shape_score), updated with evidence
diagnosis      : { hypothesis_id, confidence, reasoning_md, untested_alternatives[] }
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
````

- [ ] **Step 2: Commit**

```bash
git add skills/bigeye-investigate/references/engine.md
git commit -m "feat(investigate): add portable engine pseudocode"
```

---

## Task 6: Memo + ticket template

**Files:**
- Create: `skills/bigeye-investigate/references/memo-template.md`

- [ ] **Step 1: Write the template doc**

````markdown
# Memo + Ticket Body Templates

Renderer reads this file and substitutes values from `InvestigationResult`. v1 emits markdown to chat; v2 (Slack/Jira) maps the same placeholders.

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
- Current value: {{issue_snapshot.current_value}} (threshold: {{issue_snapshot.threshold}})
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

```markdown
**Title:** [DQ] {{issue_snapshot.metric_type}} breach on `{{issue_snapshot.table_fq}}` — {{diagnosis.hypothesis.label}}

**Severity:** {{issue_snapshot.severity}}
**Suggested team:** {{diagnosis.hypothesis.suggested_team | default("data-platform")}}

## Summary
{{diagnosis.reasoning_md}}

## Issue
- BigEye issue: I-{{display_name}}
- Table: `{{issue_snapshot.table_fq}}`
- Metric: `{{issue_snapshot.metric_type}}`
- Opened: {{issue_snapshot.opened_at}}

## Diagnosis
**{{diagnosis.hypothesis.label}}** — confidence {{diagnosis.confidence}}
Pack: `{{pack_used}}`

{{diagnosis.hypothesis.playbook_link}}

## SQL evidence
{{#trace.queries}}
### Query {{query_idx}} — {{hypothesis_id}}
```sql
{{sql}}
```
{{result_summary}}
{{/trace.queries}}

## Manual verification
{{#manual_steps}}
{{#manual_steps}}- [ ] {{.}}
{{/manual_steps}}
{{/manual_steps}}
{{^manual_steps}}_(none)_{{/manual_steps}}

---
_Generated by /bigeye-investigate. Trace: `{{trace_path}}`_
```

## Substitution rules

- `{{path.to.value}}` — direct lookup, empty string if absent.
- `{{#section}}...{{/section}}` — repeat block for each element if list, render once if truthy object, skip if null/empty.
- `{{^section}}...{{/section}}` — render only when section is falsy.
- `{{value | default("x")}}` — fallback value.
- `{{.}}` — current iteration value (used inside `{{#list}}`).

The renderer is a small string-substituter, not a full Mustache implementation. v1 implementation hand-rolls these eight patterns. If a section requires logic beyond these, add a derived field upstream in the engine, not in the template.
````

- [ ] **Step 2: Commit**

```bash
git add skills/bigeye-investigate/references/memo-template.md
git commit -m "feat(investigate): add memo + ticket body templates"
```

---

## Task 7: `_default_pack` skeleton (yaml + stub hypotheses)

**Files:**
- Create: `skills/bigeye-investigate/_default_pack/pack.yaml`
- Create: `skills/bigeye-investigate/_default_pack/hypotheses/freshness.md`
- Create: `skills/bigeye-investigate/_default_pack/hypotheses/volume.md`
- Create: `skills/bigeye-investigate/_default_pack/hypotheses/null.md`
- Create: `skills/bigeye-investigate/_default_pack/hypotheses/distribution.md`
- Create: `skills/bigeye-investigate/_default_pack/hypotheses/schema.md`
- Create: `skills/bigeye-investigate/_default_pack/hypotheses/custom.md`
- Create: `skills/bigeye-investigate/_default_pack/verification.md`

Stub hypotheses only — labels + rationale + expected_signal. Real SQL lands in Task 13.

- [ ] **Step 1: pack.yaml**

```yaml
name: _default
version: 1
priority: 0
description: Generic fallback pack. Used when no user pack matches the issue's BigEye tags.
tags: []
budget: 10
widening_threshold: 10000000
covers:
  - freshness
  - volume
  - null
  - distribution
  - schema
  - custom
```

- [ ] **Step 2: hypotheses/freshness.md (3 stubs)**

```markdown
# Freshness hypotheses — _default

---
id: upstream-loader-stalled
label: Upstream loader stalled or hung
rationale: |
  The most common freshness failure is the upstream ETL job stopped running
  or hung mid-batch. The table itself is fine; new rows simply aren't arriving.
prior: high
expected_signal: |
  MAX(loaded_at) is older than the monitor's expected freshness window. No new
  inserts in the last N hours where N >= the threshold. Other tables loaded
  by the same job also show staleness.
query_template: |
  -- TODO: replace with real query in Task 13
  SELECT MAX(loaded_at) AS last_load, COUNT(*) AS rows_total
  FROM {{table}}
  WHERE {{monitor_where}}
requires_widening: false
playbook_link: |
  Ticket the team that owns the loader. Include `last_load` and the expected
  cadence from the monitor.
---

id: scheduler-skipped
label: Scheduler skipped this run (cron misfire, dependency wait)
rationale: |
  Airflow / dbt / cron sometimes skip a run due to dependency blocks or
  paused DAGs. Table is healthy except for the gap.
prior: medium
expected_signal: |
  Loader is otherwise healthy — previous runs landed on time, future runs
  will resume. Single gap in `loaded_at` distribution.
query_template: |
  -- TODO: replace in Task 13
  SELECT DATE_TRUNC('hour', loaded_at) AS hr, COUNT(*) AS rows
  FROM {{table}}
  WHERE {{monitor_where}}
  GROUP BY 1
  ORDER BY 1 DESC
  LIMIT 50
requires_widening: false
---

id: source-stopped-emitting
label: Source system stopped emitting
rationale: |
  Source-side outage. Loader runs fine but reads empty batches.
prior: medium
expected_signal: |
  Loader logs healthy (out of scope); newest rows in the table have
  expected loaded_at but unusually low row counts per batch.
query_template: |
  -- TODO: replace in Task 13
  SELECT DATE_TRUNC('hour', loaded_at) AS hr, COUNT(*) AS rows
  FROM {{table}}
  WHERE {{monitor_where}}
  GROUP BY 1
  ORDER BY 1 DESC
  LIMIT 50
requires_widening: false
---
```

- [ ] **Step 3: hypotheses/volume.md (3 stubs)**

```markdown
# Volume hypotheses — _default

---
id: upstream-filter-changed
label: Upstream WHERE filter changed
rationale: |
  An upstream view or ETL step added/changed a filter, dropping rows from
  this table even though the source data is intact.
prior: high
expected_signal: |
  Total row count dropped but the distribution of remaining rows looks
  consistent with a filter being applied (e.g., one partition or one value
  is now zero).
query_template: |
  -- TODO: replace in Task 13
  SELECT COUNT(*) AS rows_now FROM {{table}} WHERE {{monitor_where}}
requires_widening: false
---

id: partial-load
label: Partial load — batch failed mid-run
rationale: |
  Loader started a batch but errored partway through. Some rows landed,
  some didn't.
prior: medium
expected_signal: |
  Row count is below expected but non-zero. `loaded_at` distribution shows
  a truncated tail at the most recent run.
query_template: |
  -- TODO: replace in Task 13
  SELECT MAX(loaded_at) AS last, COUNT(*) AS rows
  FROM {{table}} WHERE {{monitor_where}}
requires_widening: false
---

id: source-legitimately-decreased
label: Source data legitimately decreased
rationale: |
  No bug — the upstream system actually has less data (e.g., end of season,
  customer dropped, calendar effect).
prior: low
expected_signal: |
  Row count drop matches a similar drop in a related source-side metric.
  Distribution looks normal otherwise.
query_template: |
  -- TODO: replace in Task 13
  SELECT DATE_TRUNC('day', loaded_at) AS day, COUNT(*) AS rows
  FROM {{table}} WHERE {{monitor_where}}
  GROUP BY 1 ORDER BY 1 DESC LIMIT 60
requires_widening: false
---
```

- [ ] **Step 4: hypotheses/null.md (3 stubs)**

```markdown
# Null-rate hypotheses — _default

---
id: upstream-column-rename
label: Upstream column was renamed or removed
rationale: |
  An upstream change renamed or dropped the column, causing the ETL to
  load nulls in its place.
prior: high
expected_signal: |
  Null rate on the affected column jumped to ~100% at a discrete timestamp.
  Other columns unaffected.
query_template: |
  -- TODO: replace in Task 13
  SELECT DATE_TRUNC('hour', loaded_at) AS hr,
         SUM(CASE WHEN {{column}} IS NULL THEN 1 ELSE 0 END)*1.0/COUNT(*) AS null_rate
  FROM {{table}} WHERE {{monitor_where}}
  GROUP BY 1 ORDER BY 1 DESC LIMIT 50
requires_widening: false
---

id: schema-mismatch
label: ETL schema mismatch — column type changed
rationale: |
  Type coercion failed and the loader wrote nulls.
prior: medium
expected_signal: |
  Null rate is elevated but not 100% — only rows with the new type are
  affected.
query_template: |
  -- TODO: replace in Task 13
  SELECT 1
  FROM {{table}} WHERE {{monitor_where}} LIMIT 1
requires_widening: false
---

id: etl-drop-too-aggressive
label: ETL drop / filter step too aggressive
rationale: |
  A recent ETL change dropped rows that previously had real values, leaving
  only rows with null in this column.
prior: medium
expected_signal: |
  Null rate up AND row count down — the rows with values are the ones that
  got dropped.
query_template: |
  -- TODO: replace in Task 13
  SELECT 1 FROM {{table}} WHERE {{monitor_where}} LIMIT 1
requires_widening: false
---
```

- [ ] **Step 5: hypotheses/distribution.md (2 stubs)**

```markdown
# Distribution hypotheses — _default

---
id: new-value-introduced
label: A new value entered the distribution
rationale: |
  An upstream source added a new category/code/enum that the monitor
  didn't expect.
prior: high
expected_signal: |
  Distribution histogram has a new bucket with non-trivial weight.
query_template: |
  -- TODO: replace in Task 13
  SELECT {{column}} AS val, COUNT(*) AS rows
  FROM {{table}} WHERE {{monitor_where}}
  GROUP BY 1 ORDER BY 2 DESC LIMIT 50
requires_widening: false
---

id: value-disappeared
label: An expected value disappeared
rationale: |
  An upstream source stopped producing one of the expected values.
prior: medium
expected_signal: |
  A previously-frequent value drops to zero in the recent window while
  others stay stable.
query_template: |
  -- TODO: replace in Task 13
  SELECT 1 FROM {{table}} WHERE {{monitor_where}} LIMIT 1
requires_widening: false
---
```

- [ ] **Step 6: hypotheses/schema.md (2 stubs)**

```markdown
# Schema hypotheses — _default

---
id: column-added-upstream
label: New column added upstream
rationale: |
  Upstream system added a column; BigEye flagged the schema change.
prior: high
expected_signal: |
  INFORMATION_SCHEMA shows a new column not previously present.
query_template: |
  -- TODO: replace in Task 13
  SELECT column_name, data_type
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE table_name ILIKE '{{table}}'
requires_widening: true
---

id: column-removed-upstream
label: Column removed upstream
rationale: |
  Upstream system dropped a column.
prior: medium
expected_signal: |
  INFORMATION_SCHEMA missing a column we expected.
query_template: |
  -- TODO: replace in Task 13
  SELECT column_name FROM INFORMATION_SCHEMA.COLUMNS WHERE table_name ILIKE '{{table}}'
requires_widening: true
---
```

- [ ] **Step 7: hypotheses/custom.md (1 stub)**

```markdown
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
  -- TODO: replace in Task 13 with monitor SQL inspection
  SELECT * FROM {{table}} WHERE {{monitor_where}} LIMIT 50
requires_widening: false
---
```

- [ ] **Step 8: verification.md**

```markdown
# Manual verification — _default

## Triggers
The default pack does not trigger manual verification automatically.
User packs that target retailer/source data should add triggers here.

## Steps template
(none for default pack)

## Output
N/A
```

- [ ] **Step 9: Commit**

```bash
git add skills/bigeye-investigate/_default_pack
git commit -m "feat(investigate): add _default pack skeleton with stub hypotheses"
```

---

## Task 8: Pack lint helper + tests

**Files:**
- Create: `tools/pack_lint.py`
- Create: `tests/test_pack_lint.py`
- Create: `tests/fixtures/pack_lint_cases/good_minimal/pack.yaml`
- Create: `tests/fixtures/pack_lint_cases/good_minimal/hypotheses/freshness.md`
- Create: `tests/fixtures/pack_lint_cases/bad_missing_tags/pack.yaml`
- Create: `tests/fixtures/pack_lint_cases/bad_unique_id/pack.yaml`
- Create: `tests/fixtures/pack_lint_cases/bad_unique_id/hypotheses/freshness.md`
- Create: `tests/fixtures/pack_lint_cases/bad_filter_mirroring/pack.yaml`
- Create: `tests/fixtures/pack_lint_cases/bad_filter_mirroring/hypotheses/freshness.md`

- [ ] **Step 1: Write fixtures — good_minimal**

`tests/fixtures/pack_lint_cases/good_minimal/pack.yaml`:

```yaml
name: good_minimal
version: 1
priority: 50
description: minimal valid pack
tags: [test-tag]
covers: [freshness]
```

`tests/fixtures/pack_lint_cases/good_minimal/hypotheses/freshness.md`:

```markdown
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
```

- [ ] **Step 2: Write fixtures — bad_missing_tags**

`tests/fixtures/pack_lint_cases/bad_missing_tags/pack.yaml`:

```yaml
name: bad_missing_tags
version: 1
priority: 50
description: missing tags
covers: [freshness]
```

- [ ] **Step 3: Write fixtures — bad_unique_id**

`tests/fixtures/pack_lint_cases/bad_unique_id/pack.yaml`: identical to `good_minimal/pack.yaml` but with `name: bad_unique_id`.

`tests/fixtures/pack_lint_cases/bad_unique_id/hypotheses/freshness.md`:

```markdown
---
id: same-id
label: First
rationale: x
prior: medium
expected_signal: x
query_template: |
  SELECT 1 FROM {{table}} WHERE {{monitor_where}}
---

id: same-id
label: Second
rationale: x
prior: low
expected_signal: x
query_template: |
  SELECT 1 FROM {{table}} WHERE {{monitor_where}}
---
```

- [ ] **Step 4: Write fixtures — bad_filter_mirroring**

`tests/fixtures/pack_lint_cases/bad_filter_mirroring/pack.yaml`: as good_minimal but `name: bad_filter_mirroring`.

`tests/fixtures/pack_lint_cases/bad_filter_mirroring/hypotheses/freshness.md`:

```markdown
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
```

- [ ] **Step 5: Write the failing test**

`tests/test_pack_lint.py`:

```python
"""Tests for tools.pack_lint."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CASES_DIR = Path(__file__).parent / "fixtures" / "pack_lint_cases"


def run_lint(pack_dir: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "tools.pack_lint", str(pack_dir)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return proc.returncode, (proc.stdout + proc.stderr).lower()


CASES = [
    ("good_minimal",          0, []),
    ("bad_missing_tags",      1, ["tags"]),
    ("bad_unique_id",         1, ["unique", "same-id"]),
    ("bad_filter_mirroring",  1, ["filter mirroring", "no-filter-no-widening"]),
]


def main() -> int:
    failures = []
    for name, want_rc, want_in_output in CASES:
        pack_dir = CASES_DIR / name
        if not pack_dir.exists():
            failures.append(f"{name}: fixture dir missing")
            continue
        rc, out = run_lint(pack_dir)
        if rc != want_rc:
            failures.append(f"{name}: rc {rc} != {want_rc}; output={out!r}")
            continue
        for needle in want_in_output:
            if needle.lower() not in out:
                failures.append(f"{name}: expected {needle!r} in output; got {out!r}")
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print(f"OK — {len(CASES)} lint cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run — expect failure**

```bash
python tests/test_pack_lint.py
```

Expected: `No module named tools.pack_lint`.

- [ ] **Step 7: Implement `tools/pack_lint.py`**

```python
"""Pack lint CLI: `python -m tools.pack_lint <pack_dir>`.

Exits 0 if all checks pass with at most warnings, 1 on any error.
Prints one finding per line: `<path>: <severity>: <message>`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: PyYAML not installed. Run `pip install pyyaml`.", file=sys.stderr)
    sys.exit(2)


REQUIRED_FIELDS = ("id", "label", "rationale", "prior", "expected_signal", "query_template")


def _parse_front_matter_blocks(text: str) -> list[dict]:
    """Each block is YAML between `---` delimiters. Return list of dicts."""
    blocks: list[dict] = []
    # split on lines that are exactly `---`
    parts = re.split(r"(?m)^---\s*$", text)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Skip heading-only blocks (e.g., the leading "# Freshness hypotheses" line)
        if p.startswith("#") and "\n" not in p:
            continue
        try:
            obj = yaml.safe_load(p)
        except yaml.YAMLError:
            continue
        if isinstance(obj, dict):
            blocks.append(obj)
    return blocks


def lint(pack_dir: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    yaml_path = pack_dir / "pack.yaml"
    if not yaml_path.exists():
        errors.append(f"{yaml_path}: error: pack.yaml missing")
        return errors, warnings

    try:
        meta = yaml.safe_load(yaml_path.read_text()) or {}
    except yaml.YAMLError as e:
        errors.append(f"{yaml_path}: error: invalid YAML: {e}")
        return errors, warnings

    if meta.get("name") != pack_dir.name:
        errors.append(f"{yaml_path}: error: name {meta.get('name')!r} != dir {pack_dir.name!r}")

    if not meta.get("tags"):
        errors.append(f"{yaml_path}: error: tags must be non-empty")

    if "priority" in meta:
        p = meta["priority"]
        if not isinstance(p, int) or not 0 <= p <= 100:
            warnings.append(f"{yaml_path}: warn: priority {p!r} outside 0..100")

    covers = meta.get("covers") or []
    if not covers:
        errors.append(f"{yaml_path}: error: covers must be non-empty")

    for issue_type in covers:
        hf = pack_dir / "hypotheses" / f"{issue_type}.md"
        if not hf.exists():
            errors.append(f"{hf}: error: hypotheses file missing for issue type {issue_type!r}")
            continue
        blocks = _parse_front_matter_blocks(hf.read_text())
        seen_ids: set[str] = set()
        for i, b in enumerate(blocks):
            missing = [f for f in REQUIRED_FIELDS if f not in b]
            if missing:
                errors.append(f"{hf}: error: block #{i} missing fields: {missing}")
                continue
            hid = b.get("id")
            if hid in seen_ids:
                errors.append(f"{hf}: error: unique id violation — {hid!r} appears twice")
            seen_ids.add(hid)
            qt = b.get("query_template", "")
            rw = b.get("requires_widening", False)
            if "{{monitor_where}}" not in qt and not rw:
                errors.append(
                    f"{hf}: error: filter mirroring — hypothesis {hid!r} drops "
                    f"monitor filter without requires_widening: true"
                )
            if "TODO" in qt:
                warnings.append(f"{hf}: warn: hypothesis {hid!r} has TODO marker in query_template")
        if len(blocks) < 2:
            warnings.append(f"{hf}: warn: only {len(blocks)} hypothesis defined; engine prefers ≥2")

    return errors, warnings


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m tools.pack_lint <pack_dir>", file=sys.stderr)
        return 2
    pack_dir = Path(argv[1]).resolve()
    if not pack_dir.is_dir():
        print(f"error: not a directory: {pack_dir}", file=sys.stderr)
        return 2
    errors, warnings = lint(pack_dir)
    for w in warnings:
        print(w)
    for e in errors:
        print(e)
    if errors:
        print(f"Lint: {len(warnings)} warning(s), {len(errors)} error(s).")
        return 1
    print(f"Lint: {len(warnings)} warning(s), 0 errors. ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 8: Run — expect pass**

```bash
python tests/test_pack_lint.py
```

Expected: `OK — 4 lint cases`.

- [ ] **Step 9: Lint the `_default_pack` from Task 7 — should pass with TODO warnings**

```bash
python -m tools.pack_lint skills/bigeye-investigate/_default_pack
```

Expected: exit 0; warnings about TODO markers remaining.

- [ ] **Step 10: Commit**

```bash
git add tools/pack_lint.py tests/test_pack_lint.py tests/fixtures/pack_lint_cases
git commit -m "feat(investigate): add pack lint with fixture-driven tests"
```

---

## Task 9: Pack template render helper + tests

**Files:**
- Create: `tools/pack_render.py`
- Create: `tests/test_pack_render.py`

- [ ] **Step 1: Write the failing test**

`tests/test_pack_render.py`:

```python
"""Tests for tools.pack_render — substitutes {{var}} placeholders."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def render(template: str, vars_json: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "tools.pack_render", "--template", template, "--vars", vars_json],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout


CASES = [
    ("SELECT * FROM {{table}} WHERE {{monitor_where}}",
     '{"table":"S.T","monitor_where":"loaded_at > 1"}',
     0,
     "SELECT * FROM S.T WHERE loaded_at > 1"),
    ("count = {{n}}",
     '{"n":42}',
     0,
     "count = 42"),
    ("hello {{name}}",
     '{}',                          # missing var → empty string
     0,
     "hello "),
    ("not a template",
     '{}',
     0,
     "not a template"),
]


def main() -> int:
    failures = []
    for tmpl, vars_json, want_rc, want_out in CASES:
        rc, out = render(tmpl, vars_json)
        out = out.rstrip("\n")
        if rc != want_rc:
            failures.append((tmpl, "rc", rc, want_rc))
        if out != want_out:
            failures.append((tmpl, "out", repr(out), repr(want_out)))
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print(f"OK — {len(CASES)} render cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run — expect failure**

```bash
python tests/test_pack_render.py
```

Expected: `No module named tools.pack_render`.

- [ ] **Step 3: Implement**

`tools/pack_render.py`:

```python
"""Pack template render CLI.

Usage:
  python -m tools.pack_render --template "<tmpl>" --vars '<json>'

Substitutes {{name}} placeholders with corresponding JSON values. Missing
variables render as empty string. Prints result to stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys


PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def render(template: str, variables: dict) -> str:
    def repl(m: re.Match) -> str:
        return str(variables.get(m.group(1), ""))
    return PLACEHOLDER.sub(repl, template)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--template", required=True)
    p.add_argument("--vars", required=True)
    args = p.parse_args(argv[1:])
    try:
        variables = json.loads(args.vars)
    except json.JSONDecodeError as e:
        print(f"error: invalid --vars JSON: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(render(args.template, variables))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Run — expect pass**

```bash
python tests/test_pack_render.py
```

Expected: `OK — 4 render cases`.

- [ ] **Step 5: Commit**

```bash
git add tools/pack_render.py tests/test_pack_render.py
git commit -m "feat(investigate): add pack template render helper"
```

---

# PHASE 1 — `/bigeye-investigate` happy path

Goal: the skill, the subagent, the `/bigeye-config snow` extensions, real SQL in `_default_pack`, and the e2e replay harness covering 5 issue types.

## Task 10: `/bigeye-config snow` subcommands

**Files:**
- Modify: `skills/bigeye-config/SKILL.md` — add `snow ...` subcommand surface to the arguments table; add the procedural section.
- Modify: `skills/bigeye/references/preamble.md` — add 5th verify point.

- [ ] **Step 1: Read existing `skills/bigeye-config/SKILL.md`**

```bash
cat skills/bigeye-config/SKILL.md
```

Identify the arguments table and the `Config Files` section. We will add a `snow.*` block to the per-profile schema and a new "Snow subcommands" section.

- [ ] **Step 2: Add `snow` rows to the arguments table**

Locate the arguments table and insert after the existing rows (preserving alphabetical-ish grouping):

```markdown
| `snow show` | Print active profile's `snow` block + the connection it maps to in `~/.snowflake/config.toml` |
| `snow set <profile>` | Set `snow.profile` on active profile. Verify the connection exists. Run `snow connection test -c <profile>` |
| `snow set <profile> --warehouse <w>` | Same + set `default_warehouse` |
| `snow set <profile> --role <r>` | Same + set `default_role` |
| `snow unset` | Remove `snow` block from active profile |
| `snow verify` | Run `snow connection test` + canary `SELECT 1` + parse `SHOW GRANTS` for write privileges. Print PASS/FAIL per check |
```

- [ ] **Step 3: Update the per-profile schema example**

In the section that shows the per-profile JSON, add the `snow` block:

```json
{
  "active_profile": "prod",
  "profiles": {
    "prod": {
      "workspace_id": 42,
      "scope": { /* unchanged */ },
      "monitored_rules": [],
      "custom_hints": [],
      "snow": {
        "profile": "ro-analytics",
        "default_warehouse": "ANALYTICS_RO_WH",
        "default_role": "DATA_READER"
      }
    }
  }
}
```

Note in the field-rules paragraph: `snow` block is optional. Required by `/bigeye-investigate`; missing → /bigeye-investigate prints "No Snowflake profile configured. Run /bigeye-config snow set <profile>." and stops.

- [ ] **Step 4: Add the "Snow subcommands" procedural section**

Add a new H2 section near the bottom of `skills/bigeye-config/SKILL.md`:

````markdown
## Snow subcommands

Owns the `profiles[<active>].snow` block. Wraps the Snowflake `snow` CLI.

### `snow show`

```bash
snow connection list --format json
```

Read `profiles.json[active].snow`. Print as a small table:

```
Active profile: <name>
  snow.profile           : <profile> (in ~/.snowflake/config.toml)
  snow.default_warehouse : <w | "(unset; relies on ~/.snowflake/config.toml)">
  snow.default_role      : <r | "(unset)">

Connection test: ✓ pass | ✗ fail (<stderr>)
```

### `snow set <profile> [--warehouse <w>] [--role <r>]`

1. Verify the connection name exists:
   ```bash
   snow connection list --format json | python -c "import json,sys; ns=[c['connection_name'] for c in json.load(sys.stdin)]; print('OK' if '<profile>' in ns else 'MISSING')"
   ```
   `MISSING` → print "Error: connection `<profile>` not found in ~/.snowflake/config.toml. Fix: add it under `[connections.<profile>]`." and stop.
2. Run `snow connection test -c <profile>`. Non-zero → print stderr + "Fix: check the connection block in `~/.snowflake/config.toml`." and stop.
3. Update `profiles.json[active].snow = { profile, default_warehouse?, default_role? }`. Preserve unaffected fields.
4. Print confirmation.

### `snow unset`

Remove the `snow` block from `profiles.json[active]`. Confirm before write.

### `snow verify`

Run four checks, print PASS/FAIL per line:

1. `snow connection test -c <snow.profile>` → PASS on rc=0.
2. Run `SELECT 1` via:
   ```bash
   snow sql -c <snow.profile> --format json -q "SELECT 1 AS x"
   ```
   PASS on rc=0 AND parsed rows == `[{"x":1}]`.
3. `SHOW GRANTS TO ROLE <current_role>` (resolve role from `snow.default_role` or `snow sql -c <p> -q "SELECT CURRENT_ROLE()"`). Parse output via:
   ```bash
   snow sql -c <p> --format json -q "SHOW GRANTS TO ROLE <role>"
   ```
   Scan privileges for any of: `INSERT|UPDATE|DELETE|TRUNCATE|CREATE|DROP|ALTER|MERGE|GRANT|REVOKE`.
   PASS if none found; WARN otherwise. Never FAIL — warn-only.
4. Print summary line.

WARN message body (when write grants detected):
```
⚠️  warn: role <role> has write privileges on <object_count> objects.
   The engine's SQL guard will still reject non-SELECT queries, but a
   dedicated read-only role is strongly recommended.

   Example role setup (run as ACCOUNTADMIN once):
     CREATE ROLE DATA_READER;
     GRANT USAGE ON WAREHOUSE <wh>      TO ROLE DATA_READER;
     GRANT USAGE ON DATABASE <db>       TO ROLE DATA_READER;
     GRANT USAGE ON ALL SCHEMAS IN ...  TO ROLE DATA_READER;
     GRANT SELECT ON ALL TABLES IN ...  TO ROLE DATA_READER;
     GRANT ROLE DATA_READER             TO USER <you>;
```

## Errors

| Condition | Block |
|---|---|
| `snow` binary not installed | `Error: snow CLI not on PATH.` / `Fix: install Snowflake CLI (https://docs.snowflake.com/developer-guide/snowflake-cli/installation/installation).` / `Why: required for /bigeye-investigate.` |
| `~/.snowflake/config.toml` missing | `Error: ~/.snowflake/config.toml missing.` / `Fix: run snow connection add.` / `Why: snow.profile must reference a connection there.` |
````

- [ ] **Step 5: Update `skills/bigeye/references/preamble.md` — extend verify to 5 points**

Locate the `verify` section in `preamble.md`. Add the 5th point:

```markdown
5. Snowflake — run `/bigeye-config snow verify` and condense to one line:
   `✓ snow profile=<profile>, role=<role> (read-only ✓)` on PASS.
   `⚠ snow profile=<profile>, role=<role> (write grants detected)` on WARN.
   `✗ snow profile=<profile> (unreachable: <stderr>)` on FAIL.
```

- [ ] **Step 6: Commit**

```bash
git add skills/bigeye-config/SKILL.md skills/bigeye/references/preamble.md
git commit -m "feat(config): add /bigeye-config snow show/set/unset/verify"
```

---

## Task 11: `bigeye-investigator` subagent definition

**Files:**
- Create: `agents/bigeye-investigator/AGENT.md`

- [ ] **Step 1: Inspect existing subagent convention**

```bash
ls agents/ && find agents -name "AGENT.md" -exec head -30 {} \;
```

Note the frontmatter / tool-allowlist convention used in this repo. Follow it.

- [ ] **Step 2: Write `agents/bigeye-investigator/AGENT.md`**

```markdown
---
name: bigeye-investigator
description: Internal subagent. Runs one BigEye DQ investigation in isolation. Receives one InvestigationRequest, returns one InvestigationResult JSON object. Read-only on BigEye and Snowflake.
tools:
  - Bash
  - Read
  - Grep
  - mcp__bigeye__search_issues
  - mcp__bigeye__get_issue
  - mcp__bigeye__list_related_issues
  - mcp__bigeye__get_table_profile
  - mcp__bigeye__get_lineage_graph
  - mcp__bigeye__get_lineage_node
  - mcp__bigeye__get_upstream_root_causes
  - mcp__bigeye__list_table_issues
  - mcp__bigeye__list_entity_tags
  - mcp__bigeye__list_report_upstream_issues
---

# bigeye-investigator (subagent)

You are the BigEye investigator. You receive ONE `InvestigationRequest` and return ONE `InvestigationResult` JSON object. Nothing else.

## Inputs

The dispatching skill provides an `InvestigationRequest` as the entirety of your prompt. The shape is documented in `skills/bigeye-investigate/references/contracts.md`.

## Procedure

Follow `skills/bigeye-investigate/references/engine.md` exactly. Refer to:

- `references/contracts.md` for input/output schemas.
- `references/adapters.md` for how to call BigEye + Snowflake (MCP-first, CLI fallback per call).
- `references/readonly-guard.md` for the SQL guard you MUST apply before every `snow sql` call.

## Rules

- **Read-only.** Reject any non-SELECT query via the guard. Do NOT execute it.
- **Respect budget.** Each `snow sql` call (including widening COUNT pre-checks) consumes one budget unit. Guard rejects do NOT consume budget.
- **Mirror monitor WHERE clauses by default.** Widening requires the COUNT pre-check from `engine.md` Phase 3.
- **Stream progress.** Print one line per phase and one line per query before executing it. Format:
  ```
  [intake] fetched issue I-<id> — <metric_type> on <table_fq>
  [pack] resolved pack=<name> via tag `<tag>` (<n> candidates, priority <p> wins)
  [hypothesis] ranked <n>; top-3: <id1> (prior=<x>), <id2> (prior=<y>), <id3> (prior=<z>)
  [query <i>/<budget>] <hypothesis_id> :: <one-line SQL summary>
     → <result_summary>
  [diagnose] <confidence> confidence — <hypothesis_id>
     evidence: <n> confirming queries, <m> contradictions
  [render] returning
  ```
- **Return value is a single fenced JSON block matching `InvestigationResult`.** Anything outside the fenced JSON block is ignored by the caller.

## Failure modes

If a step fails irrecoverably (Snowflake auth after 3 retries, BigEye `resolve`/`get_issue` fail, malformed pack with no fallback), return `InvestigationResult` with:

- `diagnosis.confidence = "low"`
- `diagnosis.reasoning_md` describing the failure
- `trace` ending in the appropriate `intake_failed` | `snowflake_error` | `pack_error` | `engine_abort` event
- Do NOT crash silently.

## Tool boundaries

Allowed: everything in the frontmatter `tools` list. The MCP read-tool set covers all intake calls. `Bash` is used for `snow sql` and for the `bigeye` CLI fallback.

Denied (do not attempt — these are not in your allowlist):

- `Write`, `Edit`, `NotebookEdit`
- Any `mcp__bigeye__update_*` / `create_*` / `delete_*` / `tag_entity` / `untag_entity`
- Anything touching Jira, Asana, Slack, Gmail, Calendar, Drive, etc.

If you find yourself wanting any of these tools, you are off-procedure. Stop and return with `engine_abort`.
```

- [ ] **Step 3: Commit**

```bash
git add agents/bigeye-investigator/AGENT.md
git commit -m "feat(investigate): add bigeye-investigator subagent definition"
```

---

## Task 12: `/bigeye-investigate` skill

**Files:**
- Create: `skills/bigeye-investigate/SKILL.md`

- [ ] **Step 1: Inspect existing skill conventions**

```bash
cat skills/bigeye-rca/SKILL.md
```

Match the frontmatter, the `Follow preamble.md Steps 1–7` pattern, and the "Arguments / Procedure / State persistence / Errors" section order.

- [ ] **Step 2: Write the skill**

`skills/bigeye-investigate/SKILL.md`:

````markdown
---
name: bigeye-investigate
description: Use when the user wants to investigate, diagnose, or root-cause a BigEye data quality issue with read-only Snowflake querying — e.g. "investigate Bigeye issue 10921", "diagnose I-1234", "what's wrong with table X". Dispatches the bigeye-investigator subagent and renders the resulting memo + paste-ready ticket body. Read-only on BigEye and Snowflake.
user-invocable: true
---

# BigEye Investigate

Run a pack-driven, read-only Snowflake investigation against one BigEye DQ issue. Returns a confidence-rated resolution memo with a paste-ready ticket body. Atomic. Single-issue in v1.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call.

Per `preamble.md` Step 5: primary issue lookup is **unscoped**. Scope applies only to lineage expansion and related-issue filtering.

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `<display_name>` | Investigate issue by BigEye display ID | `/bigeye-investigate 10921` |
| `<url>` | Investigate from full BigEye issue URL | `/bigeye-investigate https://app.bigeye.com/issues/10921` |
| `<id> --internal-id` | Bypass display-name lookup | `/bigeye-investigate 42 --internal-id` |
| (no arg) | Resume `state.json.last_issue`; if empty, ask | `/bigeye-investigate` |
| `--pack <name>` | Force pack override | `/bigeye-investigate 10921 --pack sov` |
| `--snow <profile>` | Override stored `snow.profile` | `/bigeye-investigate 10921 --snow ro-analytics` |
| `--budget <n>` | Override pack/default budget | `/bigeye-investigate 10921 --budget 15` |

Global flags from `references/output.md` apply.

## Procedure

1. Follow `preamble.md` Steps 1–7.

2. Resolve issue_ref → internal_id:
   - With `--internal-id`: arg is internal_id.
   - No arg: if `state.json.last_issue` set, use it (print `Resuming I-<display_name>.`). Else ask `Which issue?` and stop.
   - Else: MCP `search_issues`. If MCP unreachable → hard-fail per `preamble.md` Step 7.B with `feature_name=display-name lookup` and Fix line `/bigeye-investigate <internal-id> --internal-id`.

3. Verify snow profile:
   - `profile = arg --snow OR profiles.json[active].snow.profile`.
   - Missing → print:
     ```
     Error: No Snowflake profile configured.
     Fix:   /bigeye-config snow set <profile>
     Why:   /bigeye-investigate requires a snow connection in profiles.json[<active>].snow.profile
     ```
     Stop.
   - Run `snow connection test -c <profile>`. Non-zero → print stderr + Fix `/bigeye-config snow verify`. Stop.

4. Build `InvestigationRequest` (request_id = fresh uuid via `python -c "import uuid; print(uuid.uuid4())"`).

5. Print one-line intent:
   ```
   Investigating I-{display_name} (pack: {pack_or_'auto'}, budget: {n}, snow: {profile}).
   Typically takes 1-3 min. Streaming progress below.
   ```

6. Spawn subagent `bigeye-investigator` with the `InvestigationRequest` as input. Subagent runs the engine and returns one JSON block matching `InvestigationResult`.

7. Validate subagent return:
   - Extract the JSON block. Validate against `references/contracts.md` shape (presence of required fields).
   - Schema-invalid → save raw to `~/.claude/bigeye-plugin/investigations/<issue_id>-<iso8601>.raw.txt`. Print:
     ```
     Error: investigator returned invalid schema.
     Raw saved: <path>
     ```
     Do NOT update `state.json.last_investigation`. Stop.

8. Render via the Renderer adapter (see `references/memo-template.md`):
   - `memo_md` = render the memo template against the result.
   - `ticket_body_md` = render the ticket template against the result.

9. Persist:
   - Write `~/.claude/bigeye-plugin/investigations/<issue_id>-<iso8601>.json` (full `InvestigationResult`).
   - Update `state.json`:
     ```
     last_issue              = <display_name>
     last_table              = <schema>.<table>
     last_workflow           = "bigeye-investigate"
     last_investigation      = { issue, request_id, at, confidence, pack_used,
                                 diagnosis_id, trace_path }
     issues[<display_name>].actions append { skill: "bigeye-investigate", at, confidence }
     ```
   - Run pruning per preamble Step 8.C.

10. Emit final block:

    ```
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

## State persistence

Per `preamble.md` Step 8.B. See step 9 above for the exact fields.

## Errors

| Condition | Block |
|---|---|
| Display-name unresolved (MCP) | `Error: BigEye returned no match for issue '<n>'.` / `Fix: re-check the URL.` / `Why: search_issues returned 0 hits.` |
| MCP unavailable + display-name arg + no `--internal-id` | per preamble Step 7.B with workaround `/bigeye-investigate <iid> --internal-id` |
| `snow` profile unconfigured | see step 3 |
| `snow connection test` fails | see step 3 |
| Subagent returns invalid schema | see step 7 |
| Subagent timeout (no return within 5 min) | print `Error: investigator timed out after 5 min. Partial trace at <path>.` Save any partial to `<id>-<ts>.partial.json`. Do not update `last_investigation`. |
| User Ctrl-C | best-effort save of any partial trace emitted; do not update `last_investigation`. |
| Out-of-scope refusals | see `references/engine.md` Errors section |

## Read-only invariant

Engine and subagent are read-only. The SQL guard at `tools/readonly_guard.py` enforces it before every `snow sql`. There is no override. Two-layer defense: layer 2 is the Snowflake role; see `/bigeye-config snow verify`.
````

- [ ] **Step 3: Commit**

```bash
git add skills/bigeye-investigate/SKILL.md
git commit -m "feat(investigate): add /bigeye-investigate skill"
```

---

## Task 13: Fill `_default_pack` with real SQL

**Files:**
- Modify: all six `skills/bigeye-investigate/_default_pack/hypotheses/*.md`

Replace every `-- TODO: replace in Task 13` placeholder with a tested SELECT that mirrors `{{monitor_where}}` or sets `requires_widening: true`. Each query must pass `assert_readonly`.

- [ ] **Step 1: Read current stubs**

```bash
cat skills/bigeye-investigate/_default_pack/hypotheses/freshness.md
```

- [ ] **Step 2: Update `freshness.md` queries**

Replace the three `query_template` blocks with:

**`upstream-loader-stalled`:**

```sql
SELECT
  MAX(loaded_at) AS last_load_at,
  COUNT(*) AS rows_total,
  DATEDIFF('hour', MAX(loaded_at), CURRENT_TIMESTAMP()) AS hours_since_last_load
FROM {{table}}
WHERE {{monitor_where}}
```

**`scheduler-skipped`:**

```sql
SELECT
  DATE_TRUNC('hour', loaded_at) AS hr,
  COUNT(*) AS rows
FROM {{table}}
WHERE {{monitor_where}}
GROUP BY 1
ORDER BY 1 DESC
LIMIT 72
```

**`source-stopped-emitting`:**

```sql
SELECT
  DATE_TRUNC('hour', loaded_at) AS hr,
  COUNT(*) AS rows
FROM {{table}}
WHERE {{monitor_where}}
GROUP BY 1
ORDER BY 1 DESC
LIMIT 72
```

- [ ] **Step 3: Update `volume.md` queries**

**`upstream-filter-changed`:**

```sql
SELECT COUNT(*) AS rows_now
FROM {{table}}
WHERE {{monitor_where}}
```

**`partial-load`:**

```sql
SELECT
  MAX(loaded_at) AS last,
  COUNT(*) AS rows,
  COUNT(DISTINCT DATE_TRUNC('hour', loaded_at)) AS hours_covered
FROM {{table}}
WHERE {{monitor_where}}
```

**`source-legitimately-decreased`:**

```sql
SELECT
  DATE_TRUNC('day', loaded_at) AS day,
  COUNT(*) AS rows
FROM {{table}}
WHERE {{monitor_where}}
GROUP BY 1
ORDER BY 1 DESC
LIMIT 60
```

- [ ] **Step 4: Update `null.md` queries**

**`upstream-column-rename`:**

```sql
SELECT
  DATE_TRUNC('hour', loaded_at) AS hr,
  SUM(CASE WHEN {{column}} IS NULL THEN 1 ELSE 0 END) * 1.0 / NULLIF(COUNT(*), 0) AS null_rate,
  COUNT(*) AS rows
FROM {{table}}
WHERE {{monitor_where}}
GROUP BY 1
ORDER BY 1 DESC
LIMIT 72
```

**`schema-mismatch`:**

```sql
SELECT
  {{column}} AS sample_value,
  COUNT(*) AS rows
FROM {{table}}
WHERE {{monitor_where}}
  AND {{column}} IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
LIMIT 20
```

**`etl-drop-too-aggressive`:**

```sql
SELECT
  COUNT(*) AS rows_now,
  SUM(CASE WHEN {{column}} IS NULL THEN 1 ELSE 0 END) AS rows_null
FROM {{table}}
WHERE {{monitor_where}}
```

- [ ] **Step 5: Update `distribution.md` queries**

**`new-value-introduced`:**

```sql
SELECT
  {{column}} AS val,
  COUNT(*) AS rows
FROM {{table}}
WHERE {{monitor_where}}
GROUP BY 1
ORDER BY 2 DESC
LIMIT 50
```

**`value-disappeared`:** identical SQL to `new-value-introduced` — the LLM scoring distinguishes which signal it matches.

- [ ] **Step 6: Update `schema.md` queries**

**`column-added-upstream`:**

```sql
SELECT column_name, data_type
FROM INFORMATION_SCHEMA.COLUMNS
WHERE table_schema || '.' || table_name = UPPER('{{table}}')
ORDER BY ordinal_position
```

Keep `requires_widening: true` (INFORMATION_SCHEMA reads don't take the monitor's WHERE clause).

**`column-removed-upstream`:** identical SQL.

- [ ] **Step 7: Update `custom.md` query**

**`business-rule-violation`:**

```sql
SELECT *
FROM {{table}}
WHERE {{monitor_where}}
LIMIT 50
```

- [ ] **Step 8: Lint — expect pass with no TODO warnings**

```bash
python -m tools.pack_lint skills/bigeye-investigate/_default_pack
```

Expected: `Lint: 0 warning(s), 0 errors. ✓` (or only the "≥2 hypothesis" warning if any file has exactly 1).

If `custom.md` warns about <2 hypotheses, that's intentional for v1 — keep it.

- [ ] **Step 9: Verify every query passes the guard**

For each `query_template` value, manually verify with `tools/readonly_guard.py`. Since templates contain `{{...}}` placeholders, render first then guard:

```bash
python -m tools.pack_render --template "$(python -c "import yaml,sys; [print(b['query_template']) for b in yaml.safe_load_all(open('skills/bigeye-investigate/_default_pack/hypotheses/freshness.md').read()) if isinstance(b,dict) and 'query_template' in b]")" --vars '{"table":"S.T","monitor_where":"1=1","column":"x"}' | xargs -0 -I {} python -m tools.readonly_guard "{}"
```

If this one-liner is too clunky in practice, just inline-test one rendered query per file by hand. The strict check happens in the e2e replay tests.

- [ ] **Step 10: Commit**

```bash
git add skills/bigeye-investigate/_default_pack/hypotheses
git commit -m "feat(investigate): fill _default pack with real diagnostic SQL"
```

---

## Task 14: E2E replay harness — case `case-freshness-default`

**Files:**
- Create: `tests/test_engine_replay.py`
- Create: `tests/fixtures/engine_replay/case-freshness-default/request.json`
- Create: `tests/fixtures/engine_replay/case-freshness-default/bigeye_responses/get_issue.json`
- Create: `tests/fixtures/engine_replay/case-freshness-default/snow_responses/*.json` (one per query hash)
- Create: `tests/fixtures/engine_replay/case-freshness-default/expected_diagnosis.json`
- Create: `tests/fixtures/engine_replay/case-freshness-default/expected_trace_events.json`

The replay harness exercises the engine *as a deterministic Python module*. Since the production engine runs inside an LLM subagent, the harness instead validates that:

1. The pack lints clean.
2. Every `query_template` in the pack renders + passes the guard for plausible substitutions.
3. Fixture inputs produce expected `result_summary` shape (heuristic match, not exact string).

This is narrower than full engine replay (the LLM scoring is non-deterministic by nature), but covers the contract surface that has to hold.

- [ ] **Step 1: Write the replay harness**

`tests/test_engine_replay.py`:

```python
"""Engine replay smoke test.

Loads pack fixtures, renders each query_template, checks the guard accepts it,
and asserts the request/response fixture files are well-formed. Does NOT
execute the LLM-driven engine loop — that lives in the live smoke checklist
under tests/scenarios.md.
"""
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: PyYAML not installed.", file=sys.stderr)
    sys.exit(2)

REPO = Path(__file__).resolve().parent.parent
CASES = Path(__file__).parent / "fixtures" / "engine_replay"
DEFAULT_PACK = REPO / "skills" / "bigeye-investigate" / "_default_pack"


def render(template: str, variables: dict) -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "tools.pack_render",
         "--template", template, "--vars", json.dumps(variables)],
        cwd=REPO, capture_output=True, text=True, check=True,
    )
    return proc.stdout


def guard(sql: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "tools.readonly_guard", sql],
        cwd=REPO, capture_output=True, text=True,
    )
    return proc.returncode, proc.stderr


def iter_hypotheses(pack_dir: Path):
    for hf in (pack_dir / "hypotheses").glob("*.md"):
        text = hf.read_text()
        for part in text.split("\n---\n"):
            try:
                obj = yaml.safe_load(part)
            except yaml.YAMLError:
                continue
            if isinstance(obj, dict) and "query_template" in obj:
                yield hf.name, obj


def main() -> int:
    failures: list[str] = []
    case_count = 0

    # 1. Every _default_pack hypothesis renders + passes the guard.
    sample_vars = {"table": "TEST_SCHEMA.TEST_TABLE", "monitor_where": "loaded_at >= DATEADD(day, -7, CURRENT_DATE)", "column": "test_col"}
    for filename, h in iter_hypotheses(DEFAULT_PACK):
        rendered = render(h["query_template"], sample_vars)
        rc, stderr = guard(rendered)
        if rc != 0:
            failures.append(f"_default_pack/{filename} :: {h['id']} :: guard failed: {stderr}")
        case_count += 1

    # 2. Every fixture case has well-formed request.json + expected_diagnosis.json.
    if CASES.exists():
        for case_dir in sorted(CASES.iterdir()):
            if not case_dir.is_dir():
                continue
            req = case_dir / "request.json"
            diag = case_dir / "expected_diagnosis.json"
            if not req.exists():
                failures.append(f"{case_dir.name}: request.json missing")
                continue
            if not diag.exists():
                failures.append(f"{case_dir.name}: expected_diagnosis.json missing")
                continue
            try:
                r = json.loads(req.read_text())
                d = json.loads(diag.read_text())
            except json.JSONDecodeError as e:
                failures.append(f"{case_dir.name}: invalid JSON: {e}")
                continue
            for f in ("issue_ref", "snow_profile", "budget"):
                if f not in r:
                    failures.append(f"{case_dir.name}/request.json: missing field {f!r}")
            for f in ("hypothesis_id", "confidence"):
                if f not in d:
                    failures.append(f"{case_dir.name}/expected_diagnosis.json: missing field {f!r}")
            case_count += 1

    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print(f"OK — {case_count} replay checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run — expect pass (covers default pack rendering even before adding fixtures)**

```bash
python tests/test_engine_replay.py
```

Expected: `OK — N replay checks` where N is the count of hypotheses in `_default_pack`.

- [ ] **Step 3: Add case-freshness-default fixture**

`tests/fixtures/engine_replay/case-freshness-default/request.json`:

```json
{
  "request_id": "01HX-test-freshness-default",
  "issue_ref": "10001",
  "internal_id_flag": false,
  "snow_profile": "ro-analytics",
  "pack_override": null,
  "budget": 10,
  "scope": { "data_sources": [], "schemas": [], "tables": [], "virtual_tables": [] }
}
```

`tests/fixtures/engine_replay/case-freshness-default/expected_diagnosis.json`:

```json
{
  "hypothesis_id": "upstream-loader-stalled",
  "confidence": "high"
}
```

- [ ] **Step 4: Re-run**

```bash
python tests/test_engine_replay.py
```

Expected: `OK — N+1 replay checks`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_engine_replay.py tests/fixtures/engine_replay/case-freshness-default
git commit -m "test(investigate): add engine replay harness + freshness fixture"
```

---

## Task 15: E2E replay — remaining four cases

**Files:**
- Create: `tests/fixtures/engine_replay/case-volume-default/request.json` + `expected_diagnosis.json`
- Create: `tests/fixtures/engine_replay/case-null-default/...`
- Create: `tests/fixtures/engine_replay/case-distribution-default/...`
- Create: `tests/fixtures/engine_replay/case-custom-default/...`

- [ ] **Step 1: Create the four fixture dirs**

For each issue type (`volume`, `null`, `distribution`, `custom`), create `request.json` matching the freshness shape with a unique `request_id` and `issue_ref`, and `expected_diagnosis.json` naming the highest-prior hypothesis in the corresponding `_default_pack/hypotheses/<type>.md`.

Example: `case-volume-default/request.json`:

```json
{
  "request_id": "01HX-test-volume-default",
  "issue_ref": "10002",
  "internal_id_flag": false,
  "snow_profile": "ro-analytics",
  "pack_override": null,
  "budget": 10,
  "scope": { "data_sources": [], "schemas": [], "tables": [], "virtual_tables": [] }
}
```

`case-volume-default/expected_diagnosis.json`:

```json
{
  "hypothesis_id": "upstream-filter-changed",
  "confidence": "high"
}
```

Repeat for `null` → `upstream-column-rename`, `distribution` → `new-value-introduced`, `custom` → `business-rule-violation`.

- [ ] **Step 2: Run**

```bash
python tests/test_engine_replay.py
```

Expected: `OK — N+5 replay checks`.

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/engine_replay/case-{volume,null,distribution,custom}-default
git commit -m "test(investigate): add replay fixtures for volume/null/distribution/custom"
```

---

## Task 16: Scenarios.md — live smoke checklist

**Files:**
- Modify: `tests/scenarios.md` — append a `## Scenario N — Investigator` section.

- [ ] **Step 1: Append a new scenario**

```markdown
## Scenario N — Investigator happy path

Run `/bigeye-investigate <id>` against three real BigEye issues per release.

### Setup
- Active profile has `snow.profile` set and `/bigeye-config snow verify` passes with no write-grant warning.
- `~/.claude/bigeye-plugin/packs/_default/` exists (auto-copied on first run).

### Run
1. `/bigeye-investigate <fresh display name>` — uses default pack.

### Pass criteria
- Memo renders with all sections (Summary, Issue context, Trace, Evidence, Suggested next steps, Untested alternatives).
- Ticket body renders as fenced markdown the developer can paste into Jira/Asana with zero structural edits.
- Trace file at `~/.claude/bigeye-plugin/investigations/<id>-<iso8601>.json` exists and contains every executed query.
- Snowflake query history (`select * from snowflake.account_usage.query_history where role_name='<role>' and start_time >= dateadd(minute, -10, current_timestamp())`) shows only `SELECT` / `SHOW` queries from the investigation window. Zero non-SELECT.
- `state.json.last_investigation` updated with `confidence`, `pack_used`, `diagnosis_id`, `trace_path`.

### Negative
- `/bigeye-investigate <id>` with `snow.profile` unset → prints the "No Snowflake profile configured" block and stops.
- `/bigeye-investigate <id>` with MCP unreachable → prints the reconnect block and stops.
- `/bigeye-investigate <id> --pack does-not-exist` → returns `confidence=low` with reason `"pack 'does-not-exist' not found"`.

## Scenario N+1 — Investigator with subagent timeout (synthetic)

(Document the procedure for manually inducing a >5 min hang by passing `--budget 1000` against a slow Snowflake warehouse. Verify the timeout error path renders the partial-trace path.)
```

- [ ] **Step 2: Commit**

```bash
git add tests/scenarios.md
git commit -m "docs(investigate): add live smoke scenarios for the investigator"
```

---

## Task 17: README + version bump

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`

- [ ] **Step 1: Update README commands table**

In `README.md`, locate the Commands table and add:

```markdown
| `/bigeye-investigate <issue>` | Read-only Snowflake-backed root-cause investigation. Returns memo + paste-ready ticket body |
| `/bigeye-pack new <name>` | Scaffold a new domain pack interactively. Includes `lint`, `list` |
```

In the Daily flow diagram, add `[v]nvestigate` to the action list under `/bigeye-roster`.

- [ ] **Step 2: Add a "What's new in 0.6.0" section**

Prepend to the existing "What's new in 0.5.0" section:

```markdown
## What's new in 0.6.0

- **`/bigeye-investigate <issue>` (new).** Read-only Snowflake investigation, pack-driven, confidence-rated memo + paste-ready ticket body. Dispatches the `bigeye-investigator` subagent.
- **Pack format + `/bigeye-pack new <name>`.** Domain knowledge (hypotheses, playbooks, manual verification) lives in `~/.claude/bigeye-plugin/packs/<name>/`, loaded by BigEye tag.
- **`/bigeye-config snow set/show/unset/verify`.** Bind a Snowflake `snow` CLI connection to each BigEye profile. `verify` warns if the role has write grants.
- **Roster `[v]` investigate action.** Recommended on diagnosable-shape issues.

## What's new in 0.5.0
```

- [ ] **Step 3: Bump version in pyproject.toml**

```toml
version = "0.6.0"
```

- [ ] **Step 4: Commit**

```bash
git add README.md pyproject.toml
git commit -m "chore: bump to 0.6.0 + document investigator and pack surface"
```

---

# PHASE 2 — Pack surface + roster integration

Goal: `/bigeye-pack new` / `lint` / `list` skill, and roster's `[v]` action.

## Task 18: `/bigeye-pack` skill templates

**Files:**
- Create: `skills/bigeye-pack/templates/pack.yaml.tmpl`
- Create: `skills/bigeye-pack/templates/hypothesis.md.tmpl`
- Create: `skills/bigeye-pack/templates/verification.md.tmpl`

- [ ] **Step 1: pack.yaml.tmpl**

```yaml
name: {{name}}
version: 1
priority: {{priority}}
description: {{description}}
tags:
{{#tags}}
  - {{.}}
{{/tags}}
budget: 10
widening_threshold: 10000000
covers:
{{#covers}}
  - {{.}}
{{/covers}}
```

- [ ] **Step 2: hypothesis.md.tmpl**

```markdown
# {{issue_type}} hypotheses — {{pack_name}}

---
id: TODO-replace-with-slug
label: {{user_pattern_line}}
rationale: |
  TODO: explain when this hypothesis fires and why it's plausible.
prior: medium
expected_signal: |
  TODO: describe what a confirming query result looks like.
query_template: |
  -- TODO: write SELECT that mirrors monitor WHERE clauses
  SELECT 1
  FROM {{table}}
  WHERE {{monitor_where}}
  LIMIT 100
requires_widening: false
playbook_link: |
  TODO: what to do when this is the diagnosis. Manual verification: ...
---
```

- [ ] **Step 3: verification.md.tmpl**

```markdown
# Manual verification — {{pack_name}}

## Triggers
<!-- Engine switches to verification mode when any of these match. Remove the comment markers to enable. -->
<!-- Example: -->
<!-- - A confirmed hypothesis has `playbook_link` containing "Manual verification:" -->

## Steps template
<!-- When switched, the engine renders this block. Use {{retailer}}, {{category}}, {{keyword}}, {{date_range}} substitutions from trace context. -->

## Output
<!-- Verification steps appear in the memo under "Manual verification required". -->
```

- [ ] **Step 4: Commit**

```bash
git add skills/bigeye-pack/templates
git commit -m "feat(pack): add pack scaffold templates"
```

---

## Task 19: `/bigeye-pack` skill

**Files:**
- Create: `skills/bigeye-pack/SKILL.md`

- [ ] **Step 1: Write the skill**

````markdown
---
name: bigeye-pack
description: Use when the user wants to create, validate, or list domain packs for /bigeye-investigate. Subcommands `new <name>`, `lint <name>`, `list`. Packs live in ~/.claude/bigeye-plugin/packs/.
user-invocable: true
---

# BigEye Pack

Scaffold and manage domain packs for `/bigeye-investigate`. A pack bundles failure-pattern knowledge for a set of BigEye-tagged tables.

Follow `skills/bigeye/references/preamble.md` Steps 1–7 before any MCP call.

## Arguments

| Invocation | Behavior |
|---|---|
| `new <name>` | Walk the user through creating a new pack; write files; run lint |
| `lint <name>` | Validate an existing pack (calls `tools/pack_lint.py`) |
| `list` | List installed packs (name, tags, priority, status) |
| (empty) | Show usage |

## Procedure — `new <name>`

1. Validate name: lowercase kebab-case (`^[a-z][a-z0-9-]*$`), not `_default`. If `~/.claude/bigeye-plugin/packs/<name>/` exists, print:
   ```
   Error: pack '<name>' already exists at <path>.
   Fix:   /bigeye-pack lint <name> to validate it, OR remove the directory first.
   ```
   Stop.

2. Ask Q1 — `One-sentence description of this pack?`

3. Ask Q2 — `BigEye tags this pack should match (comma-separated)?`
   Use `mcp__bigeye__list_tags` to autocomplete from existing tags. Accept custom values too. Require ≥1.

4. Ask Q3 — `Priority?` (multiple choice: 0 / 25 / 50 / 75; default 50). Recommend 50.

5. Ask Q4 — `Sample table this pack covers (<schema>.<table>)?` (used to validate hypothesis templates). Verify via `mcp__bigeye__search_metadata`; on no match, re-ask once, then accept anyway with a warn line.

6. Ask Q5 — `Which issue types to cover?` (multi-select; default: freshness, volume, null). Show the full list: freshness / volume / null / distribution / schema / custom.

7. For each selected issue type, ask Q6.k — `Describe one common failure pattern for {type} on {sample_table}, in one line. Press Enter to skip.` Skipping → uses the `_default` hypothesis as starter.

8. Write files:
   - `~/.claude/bigeye-plugin/packs/<name>/pack.yaml` — render `templates/pack.yaml.tmpl` with Q1-Q5 substitutions via `tools/pack_render.py`.
   - For each selected issue type:
     - `hypotheses/<type>.md` — for each Q6.k line, append a rendered `hypothesis.md.tmpl` block with `user_pattern_line` substituted. Plus one block copied from `~/.claude/bigeye-plugin/packs/_default/hypotheses/<type>.md` (first block) as a starter.
   - `verification.md` — render `templates/verification.md.tmpl`.

9. Run `python -m tools.pack_lint <pack_dir>`. Report each finding. Don't fail on warnings.

10. Print summary:
    ```
    Pack created: ~/.claude/bigeye-plugin/packs/<name>/

    Next steps:
    1. Open hypotheses/<type>.md files. Each stub has TODO markers for
       `query_template`, `expected_signal`, `playbook_link`. Fill them in.
    2. Test with: /bigeye-investigate <issue-id> --pack <name>
    3. When ready, tag tables in BigEye with one of: {tags}. The investigator
       picks the pack up automatically.

    Validate: /bigeye-pack lint <name>
    List all: /bigeye-pack list
    ```

## Procedure — `lint <name>`

Run `python -m tools.pack_lint ~/.claude/bigeye-plugin/packs/<name>`. Print stdout as-is. Exit code is propagated to the user (0 = clean, 1 = errors).

## Procedure — `list`

1. List directories under `~/.claude/bigeye-plugin/packs/`.
2. For each, parse `pack.yaml` and run `pack_lint` to get a status flag.
3. Render a table:
   ```
   Installed packs (~/.claude/bigeye-plugin/packs/):

     Name         Tags                    Priority   Covers                                  Status
     sov          sov, share-of-voice     50         freshness, volume, null, distribution   ✓
     retail-pos   pos, retail-orders      25         freshness, volume                       ⚠️ 2 stubs
     _default     —                       0          all 6 types                             ✓ (shipped)
   ```
4. Status:
   - `✓` if `pack_lint` exits 0 and zero TODO warnings
   - `⚠️ N stubs` if pack_lint warns about N TODOs
   - `✗ errors` if pack_lint exits 1

## State persistence

No state writes — read-only on `state.json`. Pack creation writes only under `~/.claude/bigeye-plugin/packs/`.

## Errors

| Condition | Block |
|---|---|
| Name invalid | `Error: pack name must be lowercase kebab-case; got '<x>'.` |
| Name is `_default` | `Error: '_default' is reserved.` |
| MCP unreachable for `list_tags` autocomplete | warn + continue (user types tags manually) |
| Pack dir already exists | see step 1 |
| Writing files fails | print the OSError + Fix line |
````

- [ ] **Step 2: Commit**

```bash
git add skills/bigeye-pack/SKILL.md
git commit -m "feat(pack): add /bigeye-pack new/lint/list skill"
```

---

## Task 20: Roster `[v]` action

**Files:**
- Modify: `skills/bigeye/references/roster.md` — add `[v]` to action handlers; update recommendation derivation; update end-of-pass summary; add the handler body.

- [ ] **Step 1: Read roster.md**

```bash
cat skills/bigeye/references/roster.md
```

Identify three sections: Action menu (string), Recommendation derivation, Action handlers, End-of-pass summary.

- [ ] **Step 2: Update the action menu string**

Find the line listing actions (e.g., `[i]mprove [c]lose ...`). Replace with:

```
[i]mprove [v]investigate [c]lose [f]laky-note [t]icket [h]int [s]kip
```

- [ ] **Step 3: Update Recommendation derivation**

Add a new row to the derivation table near the top of the action-recommendation section:

```markdown
| Issue type ∈ {freshness, volume, null, distribution, schema, custom} AND age < 24h AND no prior `bigeye-investigate` action on this issue | `v` (investigate — diagnose with Snowflake-backed pack) |
| Same type, prior `bigeye-investigate` exists with confidence ∈ {high, medium} | `t` (ticket — already diagnosed) |
```

Place this row BEFORE the existing `[i]mprove` row so it takes precedence for fresh, diagnosable-shape issues.

- [ ] **Step 4: Add the `[v]` action handler block**

Find the "Action handlers" section. Add:

````markdown
### `[v]` — investigate

1. Resolve the pack: call `PackLoader.resolve_pack_for_tags(issue.tags)`. If the resolved pack is `_default`, set `using_default = true`.
2. Read `profiles.json[active].snow.profile`. If unset, print:
   ```
   Error: No Snowflake profile configured for /bigeye-investigate.
   Fix:   /bigeye-config snow set <profile>
   Why:   roster's [v] action handler requires a snow profile.
   ```
   Treat as `[s]kip`.
3. Confirm:
   ```
   Investigate I-{id}? snow=<profile>, pack=<resolved>, budget=10. (y/n)
   ```
   If `using_default`, prepend:
   ```
   No domain pack matched tags <list>. Using _default.
   ```
4. On `y`: invoke `/bigeye-investigate <id>` as a sub-skill. Roster loop pauses until it returns. On return:
   - Append `{ skill: "bigeye-roster", action: "investigate", at: <iso8601>, confidence: <high|medium|low> }` to `state.json.issues[<id>].actions`.
   - Print `Continuing roster from I-<next_id>.`
   - Continue to next issue.
5. On `n`: same behavior as `[s]kip`.
````

- [ ] **Step 5: Update end-of-pass summary**

Find the summary block and add `investigate: <count>`:

```
Roster complete — N issues reviewed.
  close: x    flaky-note: y    ticket: z
  improve suggested: q    investigate: v    hint added: h    skip: s
```

- [ ] **Step 6: Commit**

```bash
git add skills/bigeye/references/roster.md
git commit -m "feat(roster): add [v]investigate action that hands off to /bigeye-investigate"
```

---

## Task 21: state.json `last_investigation` migration note

**Files:**
- Modify: `skills/bigeye/references/preamble.md` Step 8.B — document the new field.

- [ ] **Step 1: Read preamble Step 8.B**

```bash
sed -n '/^### 8\.B/,/^### 8\.C/p' skills/bigeye/references/preamble.md 2>/dev/null || grep -A 30 "8.B" skills/bigeye/references/preamble.md
```

- [ ] **Step 2: Add `last_investigation` field to the state.json schema example**

Append to the existing schema documentation:

```jsonc
{
  "last_workflow": "bigeye-investigate",
  "last_issue": "10921",
  "last_table": "SOV.amazon_organic_rankings",
  "last_investigation": {
    "issue": "10921",
    "request_id": "01HX...",
    "at": "2026-05-12T15:42:00Z",
    "confidence": "high",          // high | medium | low
    "pack_used": "sov",
    "diagnosis_id": "amazon-category-restructure",
    "trace_path": "investigations/10921-2026-05-12T15-42-00Z.json"
  },
  "issues": {
    "10921": {
      "actions": [
        // existing entries...
        { "skill": "bigeye-investigate", "at": "...", "confidence": "high" }
      ]
    }
  }
}
```

Backward compat: missing `last_investigation` is treated as null (no prior investigation). Any skill writing state.json MUST preserve unknown fields (already required by existing convention).

- [ ] **Step 3: Commit**

```bash
git add skills/bigeye/references/preamble.md
git commit -m "docs(state): document last_investigation field in state.json schema"
```

---

## Task 22: End-to-end manual smoke

**Files:** none modified; this is a verification gate.

- [ ] **Step 1: Run the full test suite**

```bash
python tests/test_readonly_guard.py && \
python tests/test_pack_lint.py && \
python tests/test_pack_render.py && \
python tests/test_engine_replay.py && \
python -m tools.pack_lint skills/bigeye-investigate/_default_pack
```

Expected: all five exit 0.

- [ ] **Step 2: Run skill discovery / schema validator**

```bash
python tests/test_validate_schema.py
```

Expected: PASS (skill frontmatter for new skills is valid).

- [ ] **Step 3: Manual live smoke — Scenario N from `tests/scenarios.md`**

Pick one open BigEye issue. Run `/bigeye-investigate <id>` against it. Verify against Scenario N pass criteria (memo renders, ticket body paste-ready, trace file present, zero non-SELECTs in Snowflake `query_history`, `state.json.last_investigation` updated).

If any criterion fails, do not proceed — fix the underlying skill/agent and re-run from Step 1.

- [ ] **Step 4: Commit any fixes that emerge**

Each fix gets its own commit. Do not bundle.

---

# Self-review

Plan covers spec sections as follows:

| Spec section | Task(s) |
|---|---|
| §1 Summary | covered by overall architecture in plan header |
| §2 Architecture / file layout | Tasks 1, 2, 5, 7, 10, 11, 12, 18, 19 |
| §3 Engine | Tasks 1, 2, 3, 5, 14, 15 |
| §4 Pack format | Tasks 7, 8, 13, 18, 19 |
| §5 `/bigeye-investigate` skill | Task 12 |
| §6 Subagent | Task 11 |
| §7 `/bigeye-pack` skill | Tasks 8, 18, 19 |
| §8 Existing-skill changes (roster, config snow, state.json) | Tasks 10, 20, 21 |
| §9 Read-only guard | Tasks 3, 4 |
| §10 Error taxonomy / refusals / state-write rules | Tasks 5 (engine errors), 12 (skill errors), 21 (state rules) |
| §11 Testing | Tasks 3, 8, 9, 14, 15, 16, 22 |
| §12 Rollout (Phase 0/1/2) | Phase 0 = Tasks 1-9, Phase 1 = Tasks 10-17, Phase 2 = Tasks 18-21 |
| §13 Deferrals (v1.1) | explicitly out of scope; not implemented |
| §14 SC mapping | SC-2/SC-3/SC-4 met by design; SC-1 explicitly deferred (mentioned in scenarios.md Step 1 caveat) |
| §15 NFR mapping | NFR-1 (guard) Task 3-4; NFR-2 (streaming) Task 11; NFR-3 (trace file) Task 12; NFR-4 (confidence required) Task 1 (contract requires it); NFR-5 (trigger phrases) Task 12 (skill description); NFR-6 (markdown editable) Tasks 7, 13, 18 |
| §16 Open questions resolved | embedded in design, no code action |
| §17 Deviations | embedded in design, no code action |

No placeholders, no "TODO: implement later" in plan steps (TODO markers ARE present in pack template stub files — these are intentional user-facing prompts the pack author fills in, not plan failures).

Type consistency spot-checks:
- `InvestigationResult.diagnosis.hypothesis_id` (Task 1) ↔ used in `expected_diagnosis.json` (Tasks 14, 15) ✓
- `tools/readonly_guard.py` invocation pattern (Task 3 step 5) ↔ adapter contract reference (Task 2) ↔ subagent guard rule (Task 11) ✓
- `state.json.last_investigation` field name consistent across Tasks 12, 21 ✓
- `pack.yaml` `tags` (list) vs `tag` (singular) — design and plan consistently use `tags` (list) ✓
- `bigeye-investigator` (subagent name) consistent across Tasks 11, 12, 16 ✓

---

# Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-bigeye-dq-investigator.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach?
