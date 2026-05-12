# BigEye Freeform Debug — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a prose-driven freeform debug mode to `/bigeye-investigate` so users can investigate issues without a BigEye ticket — pasted prose, optional SQL — while reusing the existing engine, subagent, and renderer.

**Architecture:** Same `/bigeye-investigate` skill, internal arg router. Numeric/URL arg → existing issue flow. Prose arg → new main-thread intake routine (`references/freeform-intake.md`) that parses prose, asks up to 3 clarifying questions, validates pasted SQL through `readonly_guard`, synthesizes an `InvestigationRequest` with `mode: "freeform"`, and dispatches the existing `bigeye-investigator` subagent. Engine Phase 1 branches on `request.mode`; Phases 2–5 are unchanged. Renderer reuses both templates with one small tweak (engine-hydrated `display_label` per query trace event).

**Tech Stack:** Python 3 (regex parsing for intake helper + tests), markdown skill prompts (router, intake procedure, engine pseudocode, templates), existing `tools/readonly_guard.py`, existing `bigeye-investigator` subagent.

**Reference:** `docs/superpowers/specs/2026-05-12-bigeye-freeform-debug-design.md`

---

## File Structure

### Create

| Path | Responsibility |
|---|---|
| `tools/freeform_intake.py` | Pure-Python parser. Input: raw arg string + flag dict. Output: `IntakeFacts` dict + `seed_sql` string. Single responsibility: extract structured facts from prose. No I/O. No MCP. No subprocess. |
| `tests/test_freeform_intake.py` | Unit tests for the parser. Plain-Python `main()` returning 0/1 per existing convention. |
| `tests/fixtures/freeform_intake_cases.json` | Fixture inputs for parser tests. |
| `tests/test_freeform_e2e.py` | End-to-end smoke test: synthesized `InvestigationRequest` → mocked `InvestigationResult` → rendered memo string. No live Snowflake / BigEye. |
| `skills/bigeye-investigate/references/freeform-intake.md` | Agent-readable procedure for Phases F0–F3 (parse, gate, guard, confirm). The skill points at this file. |

### Modify

| Path | What changes |
|---|---|
| `skills/bigeye-investigate/SKILL.md` | Arg router table, freeform flags, description-string widening, new error rows, freeform output emission. |
| `skills/bigeye-investigate/references/contracts.md` | Additive `mode`, `intake_facts`, `seed_query` on `InvestigationRequest`; `seed`, `display_label` on `query` TraceEvent. |
| `skills/bigeye-investigate/references/engine.md` | Phase 1 branches on `request.mode`; Phase 3 prepends a seed-query block; `display_label` hydration documented. |
| `skills/bigeye-investigate/references/memo-template.md` | Wrap `Current value / threshold` line in `{{#issue_snapshot.threshold}}`; replace `{{hypothesis_id}}` cell with `{{display_label}}`. |
| `agents/bigeye-investigator/AGENT.md` | Note: engine branches on `request.mode`. No tool-allowlist change. |
| `skills/bigeye/references/preamble.md` | Add `last_freeform_investigation` to the §8.B schema example; add a row to the per-skill writes table covering freeform writes. |
| `tests/scenarios.md` | Add a freeform smoke checklist. |

### Untouched (called out for reviewers)

- `tools/readonly_guard.py`
- `skills/bigeye-pack/*`
- `skills/bigeye-investigate/_default_pack/*`

---

## Task 1: Scaffold `tools/freeform_intake.py` with table extraction (TDD)

**Files:**
- Create: `tools/freeform_intake.py`
- Create: `tests/fixtures/freeform_intake_cases.json`
- Create: `tests/test_freeform_intake.py`

- [ ] **Step 1.1: Write the failing test for table extraction from prose**

Create `tests/fixtures/freeform_intake_cases.json`:

```json
{
  "table_extraction": [
    { "input": "orders look empty on PROD.ORDERS since monday", "expect_table": "PROD.ORDERS" },
    { "input": "rows missing from DB.SCHEMA.FACT_SALES", "expect_table": "DB.SCHEMA.FACT_SALES" },
    { "input": "lowercase schema.table should NOT match", "expect_table": null },
    { "input": "two tables A.X and B.Y; first wins", "expect_table": "A.X" },
    { "input": "no table here at all", "expect_table": null }
  ]
}
```

Create `tests/test_freeform_intake.py`:

```python
"""Unit tests for tools.freeform_intake."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "freeform_intake_cases.json"

sys.path.insert(0, str(REPO))
from tools import freeform_intake  # noqa: E402


def test_table_extraction(cases: list) -> list[str]:
    failures: list[str] = []
    for c in cases:
        got = freeform_intake.extract_table(c["input"])
        if got != c["expect_table"]:
            failures.append(f"table_extraction: {c['input']!r}: want {c['expect_table']!r}, got {got!r}")
    return failures


def main() -> int:
    cases = json.loads(FIXTURE.read_text())
    failures: list[str] = []
    failures += test_table_extraction(cases["table_extraction"])
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print(f"OK — freeform_intake checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 1.2: Run the test to verify it fails**

```bash
python tests/test_freeform_intake.py
```

Expected: `ModuleNotFoundError: No module named 'tools.freeform_intake'` (or similar import error).

- [ ] **Step 1.3: Write the minimal implementation**

Create `tools/freeform_intake.py`:

```python
"""Freeform-mode intake parser for /bigeye-investigate.

Pure functions over strings. No I/O. No MCP. No subprocess.

Public API:
    extract_table(prose: str) -> str | None
    extract_sql(prose: str) -> str | None
    extract_time_hint(prose: str) -> str | None
    infer_issue_type(prose: str) -> str
    parse(prose: str, flags: dict) -> dict   # returns IntakeFacts + seed_sql
"""

from __future__ import annotations

import re

# Uppercase SCHEMA.TABLE or DB.SCHEMA.TABLE. Underscores allowed, must start with letter/underscore.
_TABLE_RE = re.compile(
    r"\b[A-Z_][A-Z0-9_]*\.[A-Z_][A-Z0-9_]*(?:\.[A-Z_][A-Z0-9_]*)?\b"
)


def extract_table(prose: str) -> str | None:
    if not prose:
        return None
    m = _TABLE_RE.search(prose)
    return m.group(0) if m else None
```

- [ ] **Step 1.4: Run the test to verify it passes**

```bash
python tests/test_freeform_intake.py
```

Expected: `OK — freeform_intake checks`.

- [ ] **Step 1.5: Commit**

```bash
git add tools/freeform_intake.py tests/test_freeform_intake.py tests/fixtures/freeform_intake_cases.json
git commit -m "feat(freeform): scaffold intake parser with table extraction"
```

---

## Task 2: SQL block extraction

**Files:**
- Modify: `tools/freeform_intake.py`
- Modify: `tests/fixtures/freeform_intake_cases.json`
- Modify: `tests/test_freeform_intake.py`

- [ ] **Step 2.1: Extend fixture with SQL extraction cases**

Add to `tests/fixtures/freeform_intake_cases.json`:

```json
{
  "sql_extraction": [
    {
      "input": "ran this:\n```sql\nSELECT * FROM A.B WHERE x=1\n```\nand got 0",
      "expect_sql": "SELECT * FROM A.B WHERE x=1"
    },
    {
      "input": "ran this:\n```\nSELECT COUNT(*) FROM A.B\n```",
      "expect_sql": "SELECT COUNT(*) FROM A.B"
    },
    {
      "input": "SELECT 1 FROM dual  -- inline, no fence",
      "expect_sql": "SELECT 1 FROM dual  -- inline, no fence"
    },
    {
      "input": "no sql at all in this one",
      "expect_sql": null
    }
  ]
}
```

(Append the new key to the existing JSON object. Keep `table_extraction` intact.)

- [ ] **Step 2.2: Extend the test driver**

Append to `tests/test_freeform_intake.py` after `test_table_extraction`:

```python
def test_sql_extraction(cases: list) -> list[str]:
    failures: list[str] = []
    for c in cases:
        got = freeform_intake.extract_sql(c["input"])
        want = c["expect_sql"]
        if (got or "").strip() != (want or "").strip() if want is not None else got is not None:
            failures.append(f"sql_extraction: {c['input']!r}: want {want!r}, got {got!r}")
    return failures
```

Replace the body of `main()` to add the new call:

```python
def main() -> int:
    cases = json.loads(FIXTURE.read_text())
    failures: list[str] = []
    failures += test_table_extraction(cases["table_extraction"])
    failures += test_sql_extraction(cases["sql_extraction"])
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print(f"OK — freeform_intake checks")
    return 0
```

- [ ] **Step 2.3: Run the test to verify it fails**

```bash
python tests/test_freeform_intake.py
```

Expected: `FAIL: sql_extraction: ...` (or `AttributeError: module 'tools.freeform_intake' has no attribute 'extract_sql'`).

- [ ] **Step 2.4: Implement `extract_sql`**

Append to `tools/freeform_intake.py`:

```python
_FENCED_SQL_RE = re.compile(
    r"```(?:sql)?\s*(.*?)```",
    re.IGNORECASE | re.DOTALL,
)


def extract_sql(prose: str) -> str | None:
    if not prose:
        return None
    m = _FENCED_SQL_RE.search(prose)
    if m:
        return m.group(1).strip()
    # Unfenced: first chunk starting with SELECT or WITH, line-by-line greedy.
    lines = prose.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\s*(SELECT|WITH)\b", line, re.IGNORECASE):
            chunk: list[str] = []
            for rest in lines[i:]:
                if not rest.strip() and chunk:
                    break
                chunk.append(rest)
            return "\n".join(chunk).strip()
    return None
```

- [ ] **Step 2.5: Run the test to verify it passes**

```bash
python tests/test_freeform_intake.py
```

Expected: `OK — freeform_intake checks`.

- [ ] **Step 2.6: Commit**

```bash
git add tools/freeform_intake.py tests/test_freeform_intake.py tests/fixtures/freeform_intake_cases.json
git commit -m "feat(freeform): extract pasted SQL from prose (fenced + unfenced)"
```

---

## Task 3: Time-hint normalization

**Files:**
- Modify: `tools/freeform_intake.py`
- Modify: `tests/fixtures/freeform_intake_cases.json`
- Modify: `tests/test_freeform_intake.py`

- [ ] **Step 3.1: Add time-hint fixture cases**

Append to `tests/fixtures/freeform_intake_cases.json`:

```json
{
  "time_hint": [
    { "input": "since 2026-05-09", "expect": "loaded_at >= '2026-05-09'" },
    { "input": "last 7 days", "expect": "loaded_at >= DATEADD(day, -7, CURRENT_DATE)" },
    { "input": "last 24 hours", "expect": "loaded_at >= DATEADD(hour, -24, CURRENT_TIMESTAMP())" },
    { "input": "no time mentioned here", "expect": null }
  ]
}
```

- [ ] **Step 3.2: Extend test driver**

Append to `tests/test_freeform_intake.py`:

```python
def test_time_hint(cases: list) -> list[str]:
    failures: list[str] = []
    for c in cases:
        got = freeform_intake.extract_time_hint(c["input"])
        if got != c["expect"]:
            failures.append(f"time_hint: {c['input']!r}: want {c['expect']!r}, got {got!r}")
    return failures
```

Add `failures += test_time_hint(cases["time_hint"])` in `main()`.

- [ ] **Step 3.3: Run the test to verify it fails**

```bash
python tests/test_freeform_intake.py
```

Expected: failures complaining about missing `extract_time_hint` or wrong values.

- [ ] **Step 3.4: Implement `extract_time_hint`**

Append to `tools/freeform_intake.py`:

```python
_ISO_DATE_RE = re.compile(r"\bsince\s+(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)
_LAST_N_DAYS_RE = re.compile(r"\blast\s+(\d+)\s+days?\b", re.IGNORECASE)
_LAST_N_HOURS_RE = re.compile(r"\blast\s+(\d+)\s+hours?\b", re.IGNORECASE)


def extract_time_hint(prose: str, time_column: str = "loaded_at") -> str | None:
    if not prose:
        return None
    m = _ISO_DATE_RE.search(prose)
    if m:
        return f"{time_column} >= '{m.group(1)}'"
    m = _LAST_N_DAYS_RE.search(prose)
    if m:
        return f"{time_column} >= DATEADD(day, -{m.group(1)}, CURRENT_DATE)"
    m = _LAST_N_HOURS_RE.search(prose)
    if m:
        return f"{time_column} >= DATEADD(hour, -{m.group(1)}, CURRENT_TIMESTAMP())"
    return None
```

- [ ] **Step 3.5: Run the test to verify it passes**

```bash
python tests/test_freeform_intake.py
```

Expected: `OK — freeform_intake checks`.

- [ ] **Step 3.6: Commit**

```bash
git add tools/freeform_intake.py tests/test_freeform_intake.py tests/fixtures/freeform_intake_cases.json
git commit -m "feat(freeform): normalize time hints to monitor_where SQL"
```

---

## Task 4: Symptom-keyword → issue_type inference

**Files:**
- Modify: `tools/freeform_intake.py`
- Modify: `tests/fixtures/freeform_intake_cases.json`
- Modify: `tests/test_freeform_intake.py`

- [ ] **Step 4.1: Add fixture cases**

Append to `tests/fixtures/freeform_intake_cases.json`:

```json
{
  "issue_type": [
    { "input": "table looks stale, not updated since friday", "expect": "freshness" },
    { "input": "row count dropped, fewer rows than expected", "expect": "volume" },
    { "input": "column is null for half the rows", "expect": "null" },
    { "input": "distribution looks skewed, big spike yesterday", "expect": "distribution" },
    { "input": "schema changed, new column appeared", "expect": "schema" },
    { "input": "something feels off but I can't say what", "expect": "custom" }
  ]
}
```

- [ ] **Step 4.2: Extend test driver**

Append to `tests/test_freeform_intake.py`:

```python
def test_issue_type(cases: list) -> list[str]:
    failures: list[str] = []
    for c in cases:
        got = freeform_intake.infer_issue_type(c["input"])
        if got != c["expect"]:
            failures.append(f"issue_type: {c['input']!r}: want {c['expect']!r}, got {got!r}")
    return failures
```

Add `failures += test_issue_type(cases["issue_type"])` in `main()`.

- [ ] **Step 4.3: Run the test to verify it fails**

```bash
python tests/test_freeform_intake.py
```

Expected: failures about missing `infer_issue_type` or wrong mapping.

- [ ] **Step 4.4: Implement `infer_issue_type`**

Append to `tools/freeform_intake.py`:

```python
_KEYWORDS = {
    "freshness": [r"\bstale\b", r"\bnot updated\b", r"\bsince\b.*\b(ago|days?|hours?|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"],
    "volume": [r"\bmissing rows\b", r"\bempty\b", r"\brow count\b", r"\bfewer rows\b"],
    "null": [r"\bnull\b", r"\bblank\b", r"\bempty values\b"],
    "distribution": [r"\bskewed\b", r"\bdistribution\b", r"\boutlier\b", r"\bspike\b", r"\bdrop in\b"],
    "schema": [r"\bschema changed\b", r"\bnew column\b", r"\bcolumn type\b"],
}


def infer_issue_type(prose: str) -> str:
    if not prose:
        return "custom"
    p = prose.lower()
    for issue_type, patterns in _KEYWORDS.items():
        for pat in patterns:
            if re.search(pat, p):
                return issue_type
    return "custom"
```

- [ ] **Step 4.5: Run the test to verify it passes**

```bash
python tests/test_freeform_intake.py
```

Expected: `OK — freeform_intake checks`.

- [ ] **Step 4.6: Commit**

```bash
git add tools/freeform_intake.py tests/test_freeform_intake.py tests/fixtures/freeform_intake_cases.json
git commit -m "feat(freeform): infer issue_type from symptom keywords"
```

---

## Task 5: Top-level `parse()` with flag-override precedence

**Files:**
- Modify: `tools/freeform_intake.py`
- Modify: `tests/fixtures/freeform_intake_cases.json`
- Modify: `tests/test_freeform_intake.py`

- [ ] **Step 5.1: Add fixture for `parse()` happy paths**

Append to `tests/fixtures/freeform_intake_cases.json`:

```json
{
  "parse": [
    {
      "input": "PROD.ORDERS rows missing for last 7 days",
      "flags": {},
      "expect": {
        "table_fq": "PROD.ORDERS",
        "monitor_where": "loaded_at >= DATEADD(day, -7, CURRENT_DATE)",
        "issue_type": "volume",
        "seed_sql": null
      }
    },
    {
      "input": "something is wrong with PROD.ORDERS",
      "flags": {"table": "PROD.PAYMENTS", "since": "2026-05-09", "type": "null"},
      "expect": {
        "table_fq": "PROD.PAYMENTS",
        "monitor_where": "loaded_at >= '2026-05-09'",
        "issue_type": "null",
        "seed_sql": null
      }
    },
    {
      "input": "PROD.ORDERS empty. ran:\n```sql\nSELECT COUNT(*) FROM PROD.ORDERS\n```",
      "flags": {},
      "expect": {
        "table_fq": "PROD.ORDERS",
        "monitor_where": null,
        "issue_type": "volume",
        "seed_sql": "SELECT COUNT(*) FROM PROD.ORDERS"
      }
    },
    {
      "input": "no clue what's wrong",
      "flags": {},
      "expect": {
        "table_fq": null,
        "monitor_where": null,
        "issue_type": "custom",
        "seed_sql": null
      }
    }
  ]
}
```

- [ ] **Step 5.2: Extend test driver**

Append to `tests/test_freeform_intake.py`:

```python
def test_parse(cases: list) -> list[str]:
    failures: list[str] = []
    for c in cases:
        got = freeform_intake.parse(c["input"], c["flags"])
        want = c["expect"]
        for k in ("table_fq", "monitor_where", "issue_type", "seed_sql"):
            if got.get(k) != want.get(k):
                failures.append(
                    f"parse[{c['input']!r}, {c['flags']!r}]: field {k!r} "
                    f"want {want.get(k)!r}, got {got.get(k)!r}"
                )
    return failures
```

Add `failures += test_parse(cases["parse"])` in `main()`.

- [ ] **Step 5.3: Run the test to verify it fails**

```bash
python tests/test_freeform_intake.py
```

Expected: failures about missing `parse` or wrong fields.

- [ ] **Step 5.4: Implement `parse()`**

Append to `tools/freeform_intake.py`:

```python
def _normalize_since_flag(value: str, time_column: str = "loaded_at") -> str | None:
    """Accepts '2026-05-09' or '7d'/'24h'."""
    if not value:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return f"{time_column} >= '{value}'"
    m = re.fullmatch(r"(\d+)d", value)
    if m:
        return f"{time_column} >= DATEADD(day, -{m.group(1)}, CURRENT_DATE)"
    m = re.fullmatch(r"(\d+)h", value)
    if m:
        return f"{time_column} >= DATEADD(hour, -{m.group(1)}, CURRENT_TIMESTAMP())"
    return value  # treat as raw WHERE fragment


def parse(prose: str, flags: dict) -> dict:
    """Return IntakeFacts + seed_sql. Flags override prose-extracted values.

    flags: { "table": str?, "since": str?, "type": str? }
    """
    flags = flags or {}
    table_fq = flags.get("table") or extract_table(prose)
    monitor_where = (
        _normalize_since_flag(flags["since"]) if flags.get("since")
        else extract_time_hint(prose)
    )
    issue_type = flags.get("type") or infer_issue_type(prose)
    seed_sql = extract_sql(prose)
    return {
        "table_fq": table_fq,
        "column": None,
        "monitor_where": monitor_where,
        "issue_type": issue_type,
        "time_column": "loaded_at",
        "user_prose": prose,
        "seed_sql": seed_sql,
    }
```

- [ ] **Step 5.5: Run the test to verify it passes**

```bash
python tests/test_freeform_intake.py
```

Expected: `OK — freeform_intake checks`.

- [ ] **Step 5.6: Commit**

```bash
git add tools/freeform_intake.py tests/test_freeform_intake.py tests/fixtures/freeform_intake_cases.json
git commit -m "feat(freeform): top-level parse() with flag-override precedence"
```

---

## Task 6: Document additive fields in `contracts.md`

**Files:**
- Modify: `skills/bigeye-investigate/references/contracts.md`

- [ ] **Step 6.1: Read the current contracts**

Open `skills/bigeye-investigate/references/contracts.md`. Locate the `InvestigationRequest` block (begins `"request_id": "uuid string"`).

- [ ] **Step 6.2: Insert the additive fields**

After the closing `}` of the existing `InvestigationRequest`, add a new section:

```markdown
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
```

- [ ] **Step 6.3: Document `display_label` and `seed` on the query TraceEvent**

In the `TraceEvent` section, replace the existing `// kind: "query"` block with:

```jsonc
// kind: "query"
{ "kind": "query", "hypothesis_id": "amazon-category-restructure",
  "display_label": "`amazon-category-restructure`",     // hydrated by engine
  "sql": "SELECT ...", "row_count": 12, "ms": 1820,
  "result_summary": "12 categories, top has 0 rows in last 7 days",
  "rows_sample": [ { "category_id": "...", "rows": 0 } ],
  "seed": false                                          // true only for seed query
}
```

Below the block, add one note:

```markdown
`display_label` is rendered verbatim in the memo trace table. For pack hypotheses the engine sets it to ``` `<hypothesis_id>` ``` (backtick-wrapped). For the seed query the engine sets it to `_user-provided query_`. Older trace files written before this field existed are rendered by falling back to `hypothesis_id`.
```

- [ ] **Step 6.4: Commit**

```bash
git add skills/bigeye-investigate/references/contracts.md
git commit -m "docs(freeform): document mode/intake_facts/seed_query + display_label on TraceEvent"
```

---

## Task 7: Branch engine Phase 1 + add Phase 3 seed-query block in `engine.md`

**Files:**
- Modify: `skills/bigeye-investigate/references/engine.md`

- [ ] **Step 7.1: Replace Phase 1 with mode-aware pseudocode**

In `engine.md`, locate `## Phase 1 — Intake`. Replace the section body (everything after the header up to `## Phase 2`) with:

```markdown
## Phase 1 — Intake (no Snowflake; budget unused)

Branch on `request.mode`. Default to `"issue"` when absent.

### Issue mode (existing)

1.1  `internal_id, display_name = BigeyeClient.resolve(request.issue_ref, request.internal_id_flag)`.
     Append `{ "kind": "intake", "step": "resolve", "ok": true }`.
1.2  `issue = BigeyeClient.get_issue(internal_id)`.
     Capture metric_type, threshold, current_value, severity, opened_at, status, priority, monitor_sql, monitor_where.
1.3  `history = BigeyeClient.get_metric_history(internal_id, window=30)`.
     Populate `issue_snapshot.event_history` as `[{timestamp, value}, ...]` sorted ascending.
     Render `issue_snapshot.metric_timeline` per `bigeye/references/improve.md` §1.0.
1.4  `profile = BigeyeClient.get_table_profile(issue.table_fq)`.
1.5  `lineage = BigeyeClient.get_lineage(issue.table_fq, max_depth=5)`.
     `upstream_issues = BigeyeClient.get_upstream_issues(issue.table_fq)`.
1.6  `related = BigeyeClient.get_related_issues(internal_id, days=30)`.
1.7  `tags_table = BigeyeClient.get_tags(issue.table_id, "table")`.
     `tags_source = BigeyeClient.get_tags(issue.source_id, "source")`.

If a step fails after one retry, append `{ "kind": "intake_failed", "step": "...", "stderr": "..." }`. If 1.1 or 1.2 fail, return early with `confidence = "low"`. Other intake failures degrade.

### Freeform mode (new)

1.1f  `internal_id = null; display_name = request.issue_ref`.
      Append `{ "kind": "intake", "step": "freeform_synthesize", "ok": true }`.
1.2f  Build `issue_snapshot` from `request.intake_facts`:
      ```
      metric_type   = intake_facts.issue_type
      table_fq      = intake_facts.table_fq
      column        = intake_facts.column
      monitor_where = intake_facts.monitor_where
      monitor_sql   = null
      threshold     = null
      current_value = null
      severity      = null
      priority      = null
      status        = null
      opened_at     = intake_facts.opened_at
      event_history = []
      metric_timeline = "Freeform investigation — no historical baseline."
      ```
1.3f  Skip metric history (`event_history = []`).
1.4f  Skip table profile.
1.5f  Skip lineage and upstream issues.
1.6f  Skip related issues.
1.7f  `tags_table = BigeyeClient.get_tags(intake_facts.table_fq, "table")` — best effort. On MCP failure append `intake_failed`, set `tags_table = []`, continue.
      `tags_source = []`.

All freeform intake is local to the engine; no BigEye issue lookups.

```

- [ ] **Step 7.2: Prepend seed-query block to Phase 3**

Locate `## Phase 3 — Hypothesis loop`. Immediately after the header paragraph (before `**Initial ranking.**`), insert:

```markdown
### Phase 3.0 — Seed query (freeform only)

If `request.seed_query` is set AND `budget_used < budget`:

```
sql = request.seed_query.sql
try:
    assert_readonly(sql)
except GuardError as e:
    append { kind: "guard_reject", sql, reason: str(e),
             hypothesis_id: "seed", display_label: "_user-provided query_" }
    # budget NOT consumed; continue to Phase 3.1 with no seed
else:
    result = SnowClient.execute(sql, request.snow_profile)
    budget_used += 1
    append {
      kind: "query", hypothesis_id: "seed",
      display_label: "_user-provided query_",
      sql, row_count: result.row_count, ms: result.ms,
      result_summary: LLM_summarize(result),
      rows_sample: result.rows[:50],
      seed: true
    }
    prior_evidence_seed = result      # passed into LLM_score_evidence below
```

The seed query runs once. Its result feeds into every later `LLM_score_evidence` call as `prior_evidence_seed`. Skipping when `request.seed_query is None` is a no-op; Phase 3.1 runs as today.

```

- [ ] **Step 7.3: Document `display_label` hydration in the existing Phase 3 loop**

Inside Phase 3 (the existing `while budget_used < budget` block), update the `append { kind: "query", ... }` line to include `display_label`:

```
append { kind: "query", hypothesis_id: h.id,
         display_label: f"`{h.id}`",
         sql, row_count: result.row_count,
         ms: result.ms, result_summary: LLM_summarize(result),
         rows_sample: result.rows[:50] }
```

Add one note paragraph below the loop:

```markdown
**`display_label` invariant.** Every `query` TraceEvent has `display_label` set. For pack hypotheses it is the hypothesis id wrapped in backticks; for the seed it is `_user-provided query_`. The renderer reads this field verbatim — no per-row conditional in the template.
```

- [ ] **Step 7.4: Commit**

```bash
git add skills/bigeye-investigate/references/engine.md
git commit -m "feat(freeform): engine Phase 1 mode branch + Phase 3.0 seed query + display_label"
```

---

## Task 8: Renderer tweaks in `memo-template.md`

**Files:**
- Modify: `skills/bigeye-investigate/references/memo-template.md`

- [ ] **Step 8.1: Wrap threshold line in a section block**

Locate the line:

```
- Current value: {{issue_snapshot.current_value}} (threshold: {{issue_snapshot.threshold.kind}}={{issue_snapshot.threshold.value}})
```

Replace with:

```
{{#issue_snapshot.threshold}}
- Current value: {{issue_snapshot.current_value}} (threshold: {{issue_snapshot.threshold.kind}}={{issue_snapshot.threshold.value}})
{{/issue_snapshot.threshold}}
```

- [ ] **Step 8.2: Use `display_label` in the trace table**

Locate:

```
| {{query_idx}} | `{{hypothesis_id}}` | {{kind}} | {{result_summary}} |
```

Replace with:

```
| {{query_idx}} | {{display_label}} | {{kind}} | {{result_summary}} |
```

- [ ] **Step 8.3: Document the renderer fallback for back-compat**

Find the `## Substitution rules` section. Append a final bullet:

```
- **`display_label` fallback.** When a `query` TraceEvent lacks `display_label` (older trace files), the renderer substitutes ``` `<hypothesis_id>` ``` (backtick-wrapped) instead. The substituter implementation is responsible; templates need not change.
```

- [ ] **Step 8.4: Commit**

```bash
git add skills/bigeye-investigate/references/memo-template.md
git commit -m "feat(freeform): renderer reads display_label; wrap threshold line in section block"
```

---

## Task 9: New `references/freeform-intake.md` — agent-readable F0–F3

**Files:**
- Create: `skills/bigeye-investigate/references/freeform-intake.md`

- [ ] **Step 9.1: Write the procedure file**

Create `skills/bigeye-investigate/references/freeform-intake.md`:

```markdown
# Freeform-Mode Intake Procedure

Invoked by `/bigeye-investigate` when the arg classifier in `SKILL.md` selects freeform mode. Runs in the main thread (not in the subagent). Output: a fully-built `InvestigationRequest` with `mode: "freeform"` ready to dispatch.

## Phase F0 — Parse raw input

Shell out to `python -m tools.freeform_intake parse '<prose>' '<flags_json>'` if a CLI wrapper exists; otherwise call the equivalent of `tools.freeform_intake.parse(prose, flags)` and capture the returned dict.

Inputs:
- `prose` — the full positional argument the user passed (may include fenced SQL).
- `flags` — `{ "table": ..., "since": ..., "type": ... }` from the parsed flag set.

Output dict shape (= `IntakeFacts` + `seed_sql`):

```
{ "table_fq": str|null, "column": null,
  "monitor_where": str|null, "issue_type": str,
  "time_column": "loaded_at", "user_prose": str,
  "seed_sql": str|null }
```

Flag overrides win. The parser is best-effort; it never errors.

## Phase F1 — Required-fields gate

Required for engine dispatch: `table_fq`, `monitor_where`, `issue_type`.

Up to **three** rounds. Each round asks ONE question, in order:

**Round 1 (if `table_fq` is null):**
```
Which table is this about? (e.g. SCHEMA.TABLE)
```
Accept the answer verbatim. If still empty after the answer, continue with `table_fq = null`.

**Round 2 (if `monitor_where` is null):**
```
What time window or filter scopes the issue? Options:
  [1] last 7 days   [2] last 24 hours   [3] all rows
  [4] enter custom WHERE clause
Default time column: loaded_at — change with: column=<name>
```
Map answers:
- `1` → `loaded_at >= DATEADD(day, -7, CURRENT_DATE)`
- `2` → `loaded_at >= DATEADD(hour, -24, CURRENT_TIMESTAMP())`
- `3` → `1=1`
- `4` → accept the next user line as a raw WHERE fragment.
- `column=NAME` prefix → swap `loaded_at` for `NAME` before applying the rest.

**Round 3 (if `issue_type == "custom"` AND prose had no symptom keyword):**
```
Which kind of issue?
  [1] freshness  [2] volume  [3] null  [4] distribution  [5] schema  [6] custom
```
Map `1..6` to the six issue types.

After three rounds, if any required field is still missing:

```
Error: not enough info to investigate.
Fix:   /bigeye-investigate "<your description>" --table SCHEMA.TABLE --since 7d --type volume
Why:   need table, time scope, and issue type to run hypotheses.
```
Stop. Do not write state. Do not dispatch the subagent.

## Phase F2 — Guard pasted SQL

If `seed_sql` is non-null:

```
python -m tools.readonly_guard "<seed_sql>"
```

Non-zero exit → print:

```
Error: pasted SQL rejected by read-only guard: <stderr>.
Fix:   remove the write statement and re-run.
```
Stop.

Zero exit → keep `seed_sql` for the request.

## Phase F3 — Confirm intake

Print:

```
Freeform investigation intake:
  Table:        {table_fq}
  Filter:       {monitor_where}
  Issue type:   {issue_type}
  Pack:         {pack_override or "_default (tag lookup pending; resolved at engine Phase 2)"}
  Budget:       {budget}
  Seed query:   {"yes (will run as query #0)" if seed_sql else "no"}
Proceed? [y/n]
```

- `y` → build `InvestigationRequest`:
  ```
  {
    "request_id": "<uuid>",
    "issue_ref": "D-" + uuid4().hex[:4],
    "internal_id_flag": false,
    "snow_profile": <resolved>,
    "pack_override": <from --pack>,
    "budget": <from --budget or 10>,
    "scope": <from active profile>,
    "mode": "freeform",
    "intake_facts": { ...IntakeFacts..., "opened_at": "<now iso>" },
    "seed_query": { "sql": seed_sql, "source": "user-pasted" } if seed_sql else null
  }
  ```
- `n` → re-enter Phase F1 round 1 with prior answers preserved (do NOT re-run F0; the parsed dict is still valid).

## Hand-off

After F3 returns `y`, the skill dispatches the `bigeye-investigator` subagent with the synthesized `InvestigationRequest`. The subagent follows `engine.md` exactly — Phase 1 branches on `mode`, the rest is identical to issue mode.
```

- [ ] **Step 9.2: Commit**

```bash
git add skills/bigeye-investigate/references/freeform-intake.md
git commit -m "feat(freeform): agent-readable F0-F3 intake procedure"
```

---

## Task 10: Update `SKILL.md` — router, flags, errors, description

**Files:**
- Modify: `skills/bigeye-investigate/SKILL.md`

- [ ] **Step 10.1: Widen the skill description**

Replace the `description:` line in the frontmatter with:

```
description: Use when the user wants to investigate, diagnose, or root-cause a BigEye data quality issue (by ID or URL) OR debug a data problem described in prose with optional pasted SQL — e.g. "investigate Bigeye issue 10921", "diagnose I-1234", "what's wrong with table X", "rows missing from PROD.ORDERS since monday". Dispatches the bigeye-investigator subagent and renders the resulting memo + paste-ready ticket body. Read-only on BigEye and Snowflake.
```

- [ ] **Step 10.2: Add a Mode router table at the top of the body**

Right after the opening paragraph `Run a pack-driven, read-only Snowflake investigation...`, insert:

```markdown
## Mode router (run first)

Classify the first positional argument:

| Pattern | Mode | Next |
|---|---|---|
| `^\d+$` or `--internal-id` set | `issue` | Resolve display name → continue at step 2 below. |
| `^https?://.*bigeye\..*/issues/\d+` | `issue` | Parse internal id from URL → continue at step 2. |
| empty AND `state.json.last_issue` set | `issue` | Resume; print `Resuming I-<display_name>.` |
| empty AND `last_freeform_investigation` set AND `last_issue` empty | `freeform` | Resume freeform; jump to Phase F3 with stored facts. |
| anything else (text, spaces, code fence) | `freeform` | Follow `references/freeform-intake.md` Phases F0–F3 first; then continue at step 4 below (skip step 2 and step 3's snow check is shared). |
```

- [ ] **Step 10.3: Add freeform flags to the Arguments table**

Append rows to the existing `## Arguments` table:

```markdown
| `<prose>` | Freeform debug: describe the issue, optional fenced ```sql block | `/bigeye-investigate "PROD.ORDERS empty since monday"` |
| `--table <fq>` | Skip table clarifying question (freeform mode) | `--table PROD.ORDERS` |
| `--since <date\|interval>` | Skip filter clarifying question (freeform). ISO date or `7d`/`24h`. | `--since 7d` |
| `--type <freshness\|volume\|null\|distribution\|schema\|custom>` | Skip issue-type inference (freeform mode) | `--type volume` |
| `--ticket` | Re-emit the ticket-body block in freeform mode (memo-only by default) | `--ticket` |
```

- [ ] **Step 10.4: Wire the freeform path into the procedure**

In `## Procedure`, after step 1 (`Follow preamble.md Steps 1–7.`), add a step 1.5:

```markdown
1.5 Route by mode (see "Mode router" above). For freeform mode: follow `references/freeform-intake.md` Phases F0–F3. On exit:
   - If F1 exhausted without `table_fq` → printed error, stop.
   - If F2 rejected → printed error, stop.
   - If F3 answered `y` → an `InvestigationRequest` with `mode: "freeform"` is built. Skip step 2 (no display-name lookup). Continue at step 3 (snow profile check).
```

- [ ] **Step 10.5: Add freeform error rows**

In `## Errors`, append:

```markdown
| Freeform intake exhausts 3 rounds without `table_fq` | `Error: not enough info to investigate.` / `Fix: /bigeye-investigate "<text>" --table SCHEMA.TABLE --since 7d --type volume.` / `Why: need table, time scope, and issue type to run hypotheses.` |
| Pasted SQL fails read-only guard (main thread) | `Error: pasted SQL rejected by read-only guard: <reason>.` / `Fix: remove the write statement and re-run.` Stop. |
| Resume requested but freeform trace file deleted | Print `Note: prior freeform trace removed; starting fresh intake.` Then re-enter Phase F1 round 1. |
```

- [ ] **Step 10.6: Document freeform state writes**

In `## State persistence`, append below the existing reference to step 9:

```markdown
**Freeform mode writes** a separate top-level key `last_freeform_investigation` (schema in `bigeye/references/preamble.md` §8.B). The freeform run does NOT append to `issues[<display_name>].actions` and does NOT update `last_issue` / `last_table` / `last_workflow`. Trace file path: `~/.claude/bigeye-plugin/investigations/D-<short>-<iso8601>.json`.
```

- [ ] **Step 10.7: Add freeform output behavior to step 10**

In `## Procedure` step 10 (the "Emit final block"), append below the existing block:

```markdown
**Freeform mode emission:** memo-only by default. If `--ticket` was set OR the diagnosis confidence is `high|medium`, also emit the ticket-body block. Otherwise omit the ``` ```markdown ... ``` ``` ticket block entirely. The "Next:" line in freeform mode reads:

```
Next: /bigeye-investigate (resume) | /bigeye-investigate "<refined description>" (new run)
```
```

- [ ] **Step 10.8: Commit**

```bash
git add skills/bigeye-investigate/SKILL.md
git commit -m "feat(freeform): SKILL.md router + flags + errors + description widening"
```

---

## Task 11: Note engine branching in `AGENT.md`

**Files:**
- Modify: `agents/bigeye-investigator/AGENT.md`

- [ ] **Step 11.1: Add a note about `mode`**

In `## Procedure`, append below the existing bullets:

```markdown
- The incoming `InvestigationRequest` may set `mode: "freeform"`. Engine `Phase 1` branches on this field (see `engine.md`). Phases 2–5 are identical for both modes. You do not need additional tools — freeform intake happens in the main thread before you are dispatched.
```

- [ ] **Step 11.2: Commit**

```bash
git add agents/bigeye-investigator/AGENT.md
git commit -m "docs(freeform): note engine mode-branch in AGENT.md"
```

---

## Task 12: Update `preamble.md` state schema for freeform

**Files:**
- Modify: `skills/bigeye/references/preamble.md`

- [ ] **Step 12.1: Add `last_freeform_investigation` to the §8.B example**

In §8.B, inside the example JSON, after the `"last_investigation": { ... }` block, add:

```json
"last_freeform_investigation": {
  "synthetic_id": "D-7a3f",
  "table": "SCHEMA.TABLE",
  "request_id": "01HX...",
  "at": "2026-05-12T20:55:00Z",
  "confidence": "medium",
  "pack_used": "_default",
  "issue_type": "volume",
  "monitor_where": "loaded_at >= '2026-05-05'",
  "trace_path": "investigations/D-7a3f-2026-05-12T20-55-00Z.json"
},
```

- [ ] **Step 12.2: Add a row to the per-skill writes table**

Append to the per-skill writes table at the end of §8.B (before `Writes are atomic:`):

```markdown
| `bigeye-investigate` (freeform mode) | — | — | — | — | Sets `last_freeform_investigation` only. Does NOT touch `issues[]`, `tables[]`, `last_issue`, `last_table`, or `last_workflow`. |
```

- [ ] **Step 12.3: Document the freeform no-arg fallback**

In §8.D, append a bullet:

```markdown
- `/bigeye-investigate` with no argument → if `last_issue` set, resume issue mode (existing). Else if `last_freeform_investigation` set, resume freeform (re-print intake, ask `Proceed? [y/n]`). Else ask the user.
```

- [ ] **Step 12.4: Commit**

```bash
git add skills/bigeye/references/preamble.md
git commit -m "docs(freeform): state schema + per-skill writes row for last_freeform_investigation"
```

---

## Task 13: End-to-end smoke test for freeform render pipeline

**Files:**
- Create: `tests/test_freeform_e2e.py`

- [ ] **Step 13.1: Write the test**

Create `tests/test_freeform_e2e.py`:

```python
"""Freeform e2e smoke: parse prose -> synthesize request -> render memo.

No live Snowflake or BigEye. Mocks the InvestigationResult at the renderer
boundary by hand-constructing it and rendering through the substituter the
real Renderer would use. The point is to catch template/contract drift,
not to validate the engine itself (that lives in test_engine_replay.py).
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from tools import freeform_intake  # noqa: E402


def render(template: str, view: dict) -> str:
    """Minimal stand-in for the renderer's substituter.

    Supports: {{path.to.value}}, {{#section}}...{{/section}} (truthy non-empty),
              {{^section}}...{{/section}} (falsy/empty), iteration over lists,
              {{.}} inside iteration. Mirrors the contract documented in
              skills/bigeye-investigate/references/memo-template.md.
    """
    def lookup(view: dict, path: str):
        cur = view
        for part in path.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return None
            if cur is None:
                return None
        return cur

    # very small implementation — sufficient for the smoke test
    out = template
    # {{#section}}...{{/section}}
    for m in re.finditer(r"\{\{#([\w.]+)\}\}(.*?)\{\{/\1\}\}", template, re.DOTALL):
        path, inner = m.group(1), m.group(2)
        val = lookup(view, path)
        replacement = ""
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    item_view = {**view, **item, ".": item}
                else:
                    item_view = {**view, ".": item}
                replacement += render(inner, item_view)
        elif val:
            replacement = render(inner, {**view, **(val if isinstance(val, dict) else {})})
        out = out.replace(m.group(0), replacement)
    # {{^section}}...{{/section}}
    for m in re.finditer(r"\{\{\^([\w.]+)\}\}(.*?)\{\{/\1\}\}", template, re.DOTALL):
        path, inner = m.group(1), m.group(2)
        val = lookup(view, path)
        replacement = render(inner, view) if not val else ""
        out = out.replace(m.group(0), replacement)
    # {{path.to.value}}  and  {{.}}
    def repl(m):
        path = m.group(1)
        if path == ".":
            return str(view.get(".", ""))
        v = lookup(view, path)
        return "" if v is None else str(v)
    out = re.sub(r"\{\{([\w.]+)\}\}", repl, out)
    return out


def smoke() -> list[str]:
    failures: list[str] = []

    # 1. parse() returns a complete IntakeFacts for happy-path prose.
    facts = freeform_intake.parse(
        "PROD.ORDERS empty for last 7 days",
        flags={},
    )
    for field, expected in (
        ("table_fq", "PROD.ORDERS"),
        ("issue_type", "volume"),
        ("monitor_where", "loaded_at >= DATEADD(day, -7, CURRENT_DATE)"),
    ):
        if facts[field] != expected:
            failures.append(f"parse: {field}: want {expected!r}, got {facts[field]!r}")

    # 2. A mocked InvestigationResult renders cleanly through the freeform template.
    template_path = REPO / "skills" / "bigeye-investigate" / "references" / "memo-template.md"
    template_text = template_path.read_text()
    # Pull the memo template body between the ```markdown fences after "## Memo template".
    m = re.search(r"## Memo template[^\n]*\n+```markdown\n(.*?)\n```", template_text, re.DOTALL)
    if not m:
        failures.append("memo-template.md: could not locate ```markdown``` fence under '## Memo template'")
        return failures
    memo_template = m.group(1)

    result_view = {
        "display_name": "D-7a3f",
        "issue_snapshot": {
            "table_fq": "PROD.ORDERS",
            "metric_type": "volume",
            "column": None,
            "severity": None,
            "priority": None,
            "status": None,
            "opened_at": "2026-05-12T20:55:00Z",
            "current_value": None,
            "threshold": None,
            "metric_timeline": "Freeform investigation — no historical baseline.",
            "event_history": [],
        },
        "pack_used": "_default",
        "snow_role": "DATA_READER",
        "budget_used": 1,
        "request": {"budget": 10},
        "diagnosis": {
            "hypothesis": {
                "label": "Upstream WHERE filter changed",
                "playbook_link": "Ticket the loader owner with last_load and expected cadence.",
            },
            "confidence": "medium",
            "reasoning_md": "Row count is zero in last 7 days; consistent with an upstream filter change.",
            "suggested_next_steps_md": "- Verify upstream WHERE clauses\n- Re-run with --budget 15",
            "untested_alternatives": [],
        },
        "trace": {
            "queries": [
                {
                    "query_idx": 1,
                    "hypothesis_id": "seed",
                    "display_label": "_user-provided query_",
                    "kind": "query",
                    "result_summary": "user query returned 0 rows",
                    "seed": True,
                }
            ]
        },
        "manual_steps": None,
    }

    rendered = render(memo_template, result_view)

    # Spot-checks: render didn't crash, header includes synthetic id, seed row uses the label,
    # threshold line is absent because threshold is null.
    if "Investigation — D-7a3f" not in rendered:
        failures.append("e2e: rendered memo missing freeform header (Investigation — D-7a3f)")
    if "_user-provided query_" not in rendered:
        failures.append("e2e: rendered trace table missing _user-provided query_ label for seed row")
    if "Current value:" in rendered and "threshold" not in rendered.lower():
        # OK — Current value line might appear in other contexts. Just guarding the wrap.
        pass
    if re.search(r"Current value:[^\n]*threshold:", rendered):
        failures.append("e2e: threshold line was rendered even though threshold is null")

    return failures


def main() -> int:
    failures = smoke()
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("OK — freeform e2e smoke")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 13.2: Run the test**

```bash
python tests/test_freeform_e2e.py
```

Expected: `OK — freeform e2e smoke`. If it fails on the markdown-fence regex (Step 8 changes the template structure), adjust the regex; the test is asserting the contract documented in `memo-template.md`.

- [ ] **Step 13.3: Commit**

```bash
git add tests/test_freeform_e2e.py
git commit -m "test(freeform): e2e smoke for parse -> synthesize -> render pipeline"
```

---

## Task 14: Add freeform smoke checklist to `tests/scenarios.md`

**Files:**
- Modify: `tests/scenarios.md`

- [ ] **Step 14.1: Append a freeform scenario**

Append to `tests/scenarios.md`:

```markdown
## Scenario: Freeform debug — pasted prose + SQL (live)

Setup: a Snowflake profile that connects, any in-scope table you can read.

Run:

```
/bigeye-investigate "rows missing from <SCHEMA.TABLE> in the last 7 days. ran this:
```sql
SELECT COUNT(*) FROM <SCHEMA.TABLE> WHERE loaded_at >= DATEADD(day, -7, CURRENT_DATE)
```
"
```

Expected:
1. Intake confirmation block shows:
   - Table: `<SCHEMA.TABLE>`
   - Filter: `loaded_at >= DATEADD(day, -7, CURRENT_DATE)`
   - Issue type: `volume`
   - Pack: `_default` (or matched pack if the table has tags)
   - Budget: `10`
   - Seed query: `yes (will run as query #0)`
2. After `y`, streaming shows `[query 1/10] seed :: ...` followed by pack hypothesis queries.
3. Memo header reads `Investigation — D-<4-hex>`.
4. Trace table row 1 shows `_user-provided query_` in the second column.
5. State file `~/.claude/bigeye-plugin/state.json` now has `last_freeform_investigation` set; `last_issue` is unchanged.
6. Trace file `~/.claude/bigeye-plugin/investigations/D-<short>-<iso>.json` exists.

## Scenario: Freeform debug — guard rejects pasted SQL

Run:

```
/bigeye-investigate "fixing PROD.ORDERS: \n```sql\nDELETE FROM PROD.ORDERS\n```"
```

Expected:
```
Error: pasted SQL rejected by read-only guard: forbidden keyword 'delete'.
Fix:   remove the write statement and re-run.
```
State file is untouched.

## Scenario: Freeform debug — required-fields exhaustion

Run:

```
/bigeye-investigate "something is broken"
```

Expected: three clarifying-question rounds. If you answer all of them blank, after round 3:

```
Error: not enough info to investigate.
Fix:   /bigeye-investigate "<your description>" --table SCHEMA.TABLE --since 7d --type volume
Why:   need table, time scope, and issue type to run hypotheses.
```
```

- [ ] **Step 14.2: Commit**

```bash
git add tests/scenarios.md
git commit -m "test(freeform): manual smoke scenarios for live runs"
```

---

## Task 15: Full test run + final commit

**Files:** none (verification only)

- [ ] **Step 15.1: Run every test file in `tests/`**

```bash
python tests/test_readonly_guard.py
python tests/test_pack_lint.py
python tests/test_pack_render.py
python tests/test_engine_replay.py
python tests/test_hints.py
python tests/test_validate_schema.py
python tests/test_freeform_intake.py
python tests/test_freeform_e2e.py
```

Expected: every command exits 0 and prints `OK — ...`.

- [ ] **Step 15.2: Sanity-check `git status`**

```bash
git status -s
```

Expected: clean tree. Every change committed under tasks 1–14.

- [ ] **Step 15.3: Sanity-check `git log` for the feature branch**

```bash
git log --oneline -20
```

Expected: 14 commits for tasks 1–14 (plus the spec commit landed before this plan).

---

## Self-review notes

Coverage cross-check against `docs/superpowers/specs/2026-05-12-bigeye-freeform-debug-design.md`:

- §4 Routing → Task 10 (Mode router table, freeform flags, procedure step 1.5).
- §6 Prose intake → Task 9 (procedure prompt) + Tasks 1–5 (parser code + tests).
- §7 Contract additions → Task 6.
- §8 Engine changes → Task 7 (Phase 1 branch + Phase 3.0 seed + display_label hydration).
- §9 Renderer changes → Task 8.
- §10 State persistence → Task 12 (`last_freeform_investigation` schema + per-skill row + no-arg fallback) + Task 10.6 (skill-level note).
- §11 Read-only invariant → covered by existing `readonly_guard.py` + Task 7.2 (seed runs through `assert_readonly`).
- §12 Error handling → Task 10.5 (skill error rows) + Task 9 (intake errors) + Task 7 (engine guard_reject for seed).
- §13.1 Unit tests → Tasks 1–5.
- §13.2 Integration → Task 13.
- §13.3 Manual smoke → Task 14.
- §14 Files → all touched paths covered; §15 open questions are documentation-only and don't need code work.
