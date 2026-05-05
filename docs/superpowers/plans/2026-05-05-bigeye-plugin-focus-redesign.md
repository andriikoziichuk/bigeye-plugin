# BigEye Plugin Focus Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Repo convention:** the user owns `git commit`. Every step that says "commit" means **`git add` only**, then leave the commit to the user. Do not run `git commit` from tasks.

**Goal:** Narrow the user-facing plugin surface to three pillars (roster routine, single-monitor improve, interactive batch coverage) plus an ambient doc-grounding layer; make MCP the only required transport; hide the rest.

**Architecture:** Markdown-based Claude Code plugin. Three pillars implemented as skill files under `skills/<name>/SKILL.md`. Profile + settings JSON files extended. A new ambient skill auto-invokes for doc grounding (WebFetch over the BigEye docs site). Hidden commands stay on disk for callable escape-hatch use; only their visibility is removed.

**Tech Stack:** Claude Code plugin (markdown skills), JSON config, MCP (`bigeye` server), WebFetch for docs, Python (test scripts only).

**Spec:** `docs/superpowers/specs/2026-05-05-bigeye-plugin-focus-redesign-design.md`

---

## File Structure

### Created

| Path | Responsibility |
|---|---|
| `skills/bigeye-roster/SKILL.md` | New daily routine skill |
| `skills/bigeye-docs-grounding/SKILL.md` | New ambient doc-grounding skill |
| `skills/bigeye/references/roster.md` | Shared roster facts/recommendation/action handlers |
| `skills/bigeye/references/hints.md` | Shared hint-compile prompt + compiled-shape spec |
| `skills/bigeye/references/coverage-interactive.md` | Shared per-column proposal flow used by `bigeye-coverage` |
| `skills/bigeye/references/improve-single.md` | Shared single-monitor SQL-refinement procedure used by `bigeye-improve` |
| `skills/bigeye/references/grounding.md` | Shared doc-grounding behavior (URL conventions, citation format) |
| `tests/validate_schema.py` | Schema validator for profiles.json + settings.json |
| `tests/fixtures/hints.json` | Raw NL hint → expected compiled JSON pairs |
| `tests/skill-discovery.md` | Manual checklist mapping NL phrases → expected skill |
| `tests/scenarios.md` | Manual happy-path + error-path walkthroughs |

### Modified

| Path | What changes |
|---|---|
| `.claude-plugin/plugin.json` | Version `0.4.0` → `0.5.0`; description rewritten around the three pillars |
| `README.md` | Surface trimmed to three pillars + `/bigeye-config`; hidden commands no longer listed; CLI install dropped from required deps |
| `skills/bigeye-config/SKILL.md` | New subcommands (`hints …`, `virtual-tables …`); name→id resolution; schema migration support; CLI references demoted |
| `skills/bigeye-improve/SKILL.md` | New `<monitor_id>` arg; single-monitor procedure references `improve-single.md`; existing table mode preserved |
| `skills/bigeye-coverage/SKILL.md` | Rewritten as interactive batch proposal driven by `coverage-interactive.md` |
| `skills/bigeye/references/preamble.md` | Schema reader updates (`scope.tables: [{id,name}]`, `monitored_rules`, `virtual_tables`, `custom_hints`); MCP-required reconnect hint; CLI fallback paths trimmed |
| `skills/bigeye/references/output.md` | Add roster render template + per-issue render; add doc citation footer convention |
| `skills/bigeye/SKILL.md` (description only) | Remove from user-visible surface (description tweak — keeps user-invocable false) |
| `skills/bigeye-rca/SKILL.md` (description only) | Remove from user-visible surface |
| `skills/bigeye-today/SKILL.md` (description only) | Remove from user-visible surface |
| `skills/bigeye-table/SKILL.md` (description only) | Remove from user-visible surface |
| `skills/bigeye-triage/SKILL.md` (description only) | Remove from user-visible surface |
| `skills/bigeye-incidents/SKILL.md` (description only) | Remove from user-visible surface |
| `skills/bigeye-ticket/SKILL.md` (description only) | Remove from user-visible surface |
| `skills/bigeye-deploy/SKILL.md` (description only) | Keep callable; trim docs visibility |

Each `SKILL.md` "hidden" change is a frontmatter `description:` rewrite that emphasizes "(internal — invoked by other skills)" so the model does not surface it spontaneously, while leaving `user-invocable: true` so direct `/bigeye-rca` etc. still work.

---

## Phase 1 — Foundation

### Task 1: Bump plugin manifest

**Files:**
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/.claude-plugin/plugin.json`

- [ ] **Step 1.1: Update plugin.json**

Replace contents with:

```json
{
  "name": "bigeye-plugin",
  "version": "0.5.0",
  "description": "BigEye data observability plugin for Claude Code — daily roster routine, single-monitor improve, batch coverage proposal, and ambient docs grounding.",
  "author": {
    "name": "Andrii Koziichuk"
  }
}
```

- [ ] **Step 1.2: Stage**

```bash
git add .claude-plugin/plugin.json
```

---

### Task 2: Extend `preamble.md` for new schema

The reader logic must accept the new profile schema (scope members as `{id, name}` pairs, plus `monitored_rules`, `virtual_tables`, `custom_hints`) and tolerate the old shape during migration. It must also stop pretending the BigEye CLI is required: emit the MCP reconnect hint when MCP is unreachable.

**Files:**
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/preamble.md`

- [ ] **Step 2.1: Update Step 1.A "Locate the file" — accept new schema, migrate old**

Replace the section starting `If the loaded profile contains a non-empty \`tags\` field…` with the following:

```markdown
On load, normalize the profile into the v0.5 shape in memory:

- `scope.data_sources`, `scope.schemas`, `scope.tables`, `scope.virtual_tables`, `monitored_rules` — arrays of `{id, name}` objects.
- `custom_hints` — array of `{scope, target_id, target_name, raw, compiled, created_at}`.

Backward-compat reads (do **not** rewrite the file on disk; only project to v0.5 in memory):

- Legacy `data_source_ids: [int]` → `scope.data_sources: [{id, name: ""}]`.
- Legacy `table_ids: [int]` and `table_names: [str]` → `scope.tables`. Names without IDs get `id: null` and are flagged "needs resolve".
- Legacy `schema_names: [str]` → `scope.schemas: [{id: null, name}]`.
- Legacy `tags` (any value) → strip from working copy, print the existing one-time tag-removal note.
- Missing `monitored_rules` / `virtual_tables` / `custom_hints` → default to `[]`.

Print once per session if any legacy keys were normalized:

`Note: profile {name} uses pre-0.5 schema. Run \`/bigeye-config edit {name}\` to upgrade on disk.`
```

- [ ] **Step 2.2: Update Step 1.E "Build the parameter map"**

Replace the table contents to read:

```markdown
| Profile field | MCP parameter |
|---|---|
| `workspace_id` | `workspace_id` |
| `scope.data_sources[*].id` | `data_source_ids` (or `source_ids` if the tool requires it) |
| `scope.tables[*].id` | `table_ids` |
| `scope.virtual_tables[*].id` | `virtual_table_ids` (when the tool accepts it; otherwise omit and document) |
| `scope.schemas[*].name` | `schema_names` |
| `monitored_rules[*].id` | `dimension_ids` (when the tool accepts it; else apply post-filter) |
```

Remove the entire `For CLI calls …` paragraph that follows. Replace it with:

```markdown
The plugin is MCP-only for the v0.5 user-facing pillars. CLI fallback paths in this preamble apply only to legacy hidden skills.
```

- [ ] **Step 2.3: Add MCP-required reconnect block to Step 7**

Append at the end of Step 7 (the MCP detection step). Show this verbatim:

```markdown
### 7.E MCP-required pillars

The skills `bigeye-roster`, `bigeye-improve`, `bigeye-coverage`, and `bigeye-config` (for hint compile / name resolution) require MCP. When `MCP_AVAILABLE=false`, those skills MUST hard-fail by printing:

    MCP unreachable. Try:
      1. /mcp reconnect bigeye
      2. Retry the command
    If still failing: see bigeye-mcp-install.md

and stop. Do not attempt CLI fallback for these pillars.
```

- [ ] **Step 2.4: Run schema validator (will not exist yet — expect failure)**

```bash
python -m tests.validate_schema 2>&1 | head
```

Expected: `ModuleNotFoundError` or `tests/validate_schema.py` not found. (Validator is built in Task 16. We add this step now to wire the contract; it passes once Task 16 lands.)

- [ ] **Step 2.5: Stage**

```bash
git add skills/bigeye/references/preamble.md
```

---

## Phase 2 — Config skill extensions

### Task 3: Add custom-hints reference (`hints.md`)

The hint-compile prompt + compiled-shape spec lives in a shared reference so `/bigeye-config hints add` and `bigeye-roster` (when offering hint-add as an action) can both reuse it.

**Files:**
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/hints.md`

- [ ] **Step 3.1: Create the reference file**

Write the file with the following content:

````markdown
# Custom Hints — compile + storage spec

Custom hints are advisory inputs the roster analyzer surfaces as facts when an open issue matches their `scope` and `target_id`. They never auto-close anything.

## Storage shape

```json
{
  "scope": "table" | "monitor",
  "target_id": <int>,
  "target_name": "<string>",
  "raw": "<verbatim user NL>",
  "compiled": <one of the three shapes below>,
  "created_at": "<iso8601>"
}
```

## Three compiled shapes (the only ones allowed)

### `noise_threshold`

```json
{ "type": "noise_threshold", "metric": "<row_count|null_pct|freshness_seconds|...>", "delta_pct_max": <float> }
```

Use when the user expresses "ignore deltas under X%" or "noise floor of Y%". Roster surfaces a fact: `User noise floor for {metric}: {delta_pct_max}%`. Roster compares the issue's current delta against `delta_pct_max`; if smaller, recommendation reads "within user noise floor — close suggested".

### `expected_pattern`

```json
{ "type": "expected_pattern", "when": "weekend|weekday|hour_<H>|day_<DOW>", "metric": "<metric>" }
```

Use when the user says "weekend spikes are expected for X" or "every Sunday batch lag". Roster matches issue `opened_at` against `when` and surfaces `Matches expected pattern: {when}` if applicable.

### `context`

```json
{ "type": "context", "text": "<user's verbatim text>" }
```

Use when the NL doesn't clearly map to threshold or schedule. Roster surfaces the text verbatim under `Custom hint:`. No pattern matching.

## Compile prompt (used by `/bigeye-config hints add`)

Given user NL, scope (`table` or `monitor`), and the resolved `target_name`:

1. Try to detect a `noise_threshold` shape. Trigger words: `ignore`, `noise`, `under`, `below`, `<`, percentage references combined with a metric name.
2. Else try `expected_pattern`. Trigger words: `weekend`, `weekday`, `Sunday`, `every Monday`, `hour`, `morning`, `nightly batch`.
3. Else fall back to `context` with the verbatim text.
4. If multiple shapes match, ask the user to disambiguate. Do not silently pick.
5. If the metric name in a `noise_threshold` is ambiguous (e.g. user said "delta" without specifying), ask. Do not guess.

Always show the compiled JSON to the user and ask `Save this hint? (y/n)` before writing. Refuse to save if user replies anything other than `y`/`yes`.
````

- [ ] **Step 3.2: Stage**

```bash
git add skills/bigeye/references/hints.md
```

---

### Task 4: Add hint compilation fixture + validator stub

A pytest-style suite is overkill for this plugin. Use a tiny stand-alone Python script that loads the fixture file, runs each `raw` through a deterministic compile (a regex-based fast path for the `noise_threshold` and `expected_pattern` cases), and asserts JSON equality. The deterministic compile mirrors the preamble's compile prompt for the unambiguous cases the fixture covers.

**Files:**
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/tests/__init__.py`
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/tests/fixtures/hints.json`
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/tests/test_hints.py`

- [ ] **Step 4.1: Create fixture**

`tests/fixtures/hints.json`:

```json
[
  {
    "raw": "ignore deltas under 2% on row_count",
    "expected_compiled": {
      "type": "noise_threshold",
      "metric": "row_count",
      "delta_pct_max": 2.0
    }
  },
  {
    "raw": "noise floor of 0.5% for null_pct",
    "expected_compiled": {
      "type": "noise_threshold",
      "metric": "null_pct",
      "delta_pct_max": 0.5
    }
  },
  {
    "raw": "weekend spikes are expected for freshness_seconds",
    "expected_compiled": {
      "type": "expected_pattern",
      "when": "weekend",
      "metric": "freshness_seconds"
    }
  },
  {
    "raw": "team renames cohorts every Monday morning",
    "expected_compiled": {
      "type": "context",
      "text": "team renames cohorts every Monday morning"
    }
  }
]
```

- [ ] **Step 4.2: Create empty package marker**

`tests/__init__.py`:

```python
```

- [ ] **Step 4.3: Write failing test**

`tests/test_hints.py`:

```python
import json
import re
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "hints.json"

NOISE_RE = re.compile(
    r"(?:ignore\s+deltas?\s+under|noise\s+floor\s+of)\s+([\d.]+)\s*%\s+(?:on|for)\s+(\w+)",
    re.IGNORECASE,
)
WEEKEND_RE = re.compile(
    r"weekend\s+spikes?\s+are\s+expected\s+(?:on|for)\s+(\w+)",
    re.IGNORECASE,
)


def compile_hint(raw: str) -> dict:
    m = NOISE_RE.search(raw)
    if m:
        return {
            "type": "noise_threshold",
            "metric": m.group(2),
            "delta_pct_max": float(m.group(1)),
        }
    m = WEEKEND_RE.search(raw)
    if m:
        return {
            "type": "expected_pattern",
            "when": "weekend",
            "metric": m.group(1),
        }
    return {"type": "context", "text": raw}


def main() -> int:
    cases = json.loads(FIXTURE.read_text())
    failures = []
    for case in cases:
        got = compile_hint(case["raw"])
        if got != case["expected_compiled"]:
            failures.append((case["raw"], got, case["expected_compiled"]))
    if failures:
        for raw, got, want in failures:
            print(f"FAIL: {raw!r}\n  got:  {got}\n  want: {want}")
        return 1
    print(f"OK — {len(cases)} hint cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4.4: Run, verify pass**

```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && python -m tests.test_hints
```

Expected: `OK — 4 hint cases`.

- [ ] **Step 4.5: Stage**

```bash
git add tests/__init__.py tests/fixtures/hints.json tests/test_hints.py
```

---

### Task 5: Schema validator

**Files:**
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/tests/validate_schema.py`
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/tests/fixtures/profiles_v05.json`
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/tests/fixtures/profiles_legacy.json`
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/tests/fixtures/settings_v05.json`
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/tests/test_validate_schema.py`

- [ ] **Step 5.1: Create v0.5 profile fixture**

`tests/fixtures/profiles_v05.json`:

```json
{
  "active_profile": "prod",
  "profiles": {
    "prod": {
      "workspace_id": 123,
      "scope": {
        "data_sources":   [{"id": 12, "name": "snowflake_prod"}],
        "schemas":        [{"id": 34, "name": "analytics"}],
        "tables":         [{"id": 101, "name": "orders"}],
        "virtual_tables": [{"id": 55, "name": "active_users_30d"}]
      },
      "monitored_rules": [{"id": 1, "name": "freshness"}],
      "custom_hints": [
        {
          "scope": "table",
          "target_id": 101,
          "target_name": "orders",
          "raw": "ignore deltas under 2% on row_count",
          "compiled": {"type": "noise_threshold", "metric": "row_count", "delta_pct_max": 2.0},
          "created_at": "2026-05-05T10:00:00Z"
        }
      ]
    }
  }
}
```

- [ ] **Step 5.2: Create legacy profile fixture**

`tests/fixtures/profiles_legacy.json`:

```json
{
  "default_profile": "work-area",
  "profiles": {
    "work-area": {
      "workspace_id": 42,
      "data_source_ids": [17],
      "table_ids": [],
      "table_names": ["orders_main"],
      "schema_names": []
    }
  }
}
```

- [ ] **Step 5.3: Create v0.5 settings fixture**

`tests/fixtures/settings_v05.json`:

```json
{
  "_meta": { "version": "0.5.0", "upgrade_seen": false },
  "slack": { "channel": "#data-quality-alerts", "mention_group": "@data-oncall", "critical_only": true },
  "severity": { "critical_ack_hours": 4, "critical_related_count": 3, "warning_ack_hours": 24 },
  "triage": { "max_issues": 50, "default_brief_rows": 10 },
  "deploy": { "default_lookback_days": 7, "tag": "deployed-by-plugin" },
  "view": { "default_view": "brief" },
  "docs": { "base_url": "https://docs.bigeye.com" },
  "roster": { "batch_size": 5, "max_facts_per_issue": 6 }
}
```

- [ ] **Step 5.4: Write the validator**

`tests/validate_schema.py`:

```python
"""Schema validators for BigEye plugin config files.

Run as: python -m tests.validate_schema <profiles.json> <settings.json>
Returns exit 0 on success, 1 on validation error (with messages).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ALLOWED_HINT_TYPES = {"noise_threshold", "expected_pattern", "context"}


def _is_id_name(obj: Any) -> bool:
    return (
        isinstance(obj, dict)
        and isinstance(obj.get("name"), str)
        and (obj.get("id") is None or isinstance(obj["id"], int))
    )


def validate_profile(p: dict, name: str, errors: list[str]) -> None:
    if not isinstance(p.get("workspace_id"), int):
        errors.append(f"profile {name}: workspace_id must be int")
    legacy = any(k in p for k in ("data_source_ids", "table_ids", "table_names", "schema_names", "tags"))
    has_v05_scope = isinstance(p.get("scope"), dict)
    if not legacy and not has_v05_scope:
        errors.append(f"profile {name}: missing scope (and no legacy keys)")
    if has_v05_scope:
        scope = p["scope"]
        for key in ("data_sources", "schemas", "tables", "virtual_tables"):
            arr = scope.get(key, [])
            if not isinstance(arr, list):
                errors.append(f"profile {name}.scope.{key}: must be array")
                continue
            for i, item in enumerate(arr):
                if not _is_id_name(item):
                    errors.append(
                        f"profile {name}.scope.{key}[{i}]: must be {{id, name}}"
                    )
        rules = p.get("monitored_rules", [])
        if not isinstance(rules, list):
            errors.append(f"profile {name}.monitored_rules: must be array")
        else:
            for i, item in enumerate(rules):
                if not _is_id_name(item):
                    errors.append(
                        f"profile {name}.monitored_rules[{i}]: must be {{id, name}}"
                    )
        for i, hint in enumerate(p.get("custom_hints", []) or []):
            ctx = f"profile {name}.custom_hints[{i}]"
            if not isinstance(hint, dict):
                errors.append(f"{ctx}: must be object")
                continue
            if hint.get("scope") not in ("table", "monitor"):
                errors.append(f"{ctx}.scope: must be 'table' or 'monitor'")
            if not isinstance(hint.get("raw"), str):
                errors.append(f"{ctx}.raw: must be string")
            compiled = hint.get("compiled")
            if not isinstance(compiled, dict) or compiled.get("type") not in ALLOWED_HINT_TYPES:
                errors.append(
                    f"{ctx}.compiled.type: must be one of {sorted(ALLOWED_HINT_TYPES)}"
                )
            ts = hint.get("created_at")
            if not isinstance(ts, str):
                errors.append(f"{ctx}.created_at: must be ISO8601 string")
            else:
                try:
                    datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    errors.append(f"{ctx}.created_at: failed ISO parse: {ts}")


def validate_profiles_file(path: Path) -> list[str]:
    errors: list[str] = []
    data = json.loads(path.read_text())
    active = data.get("active_profile") or data.get("default_profile")
    profiles = data.get("profiles") or {}
    if not isinstance(profiles, dict) or not profiles:
        errors.append("profiles: must be non-empty object")
        return errors
    if active and active not in profiles:
        errors.append(f"active_profile {active!r} missing from profiles")
    for name, p in profiles.items():
        validate_profile(p, name, errors)
    return errors


def validate_settings_file(path: Path) -> list[str]:
    errors: list[str] = []
    data = json.loads(path.read_text())
    required = {
        "_meta": dict,
        "slack": dict,
        "severity": dict,
        "deploy": dict,
        "view": dict,
        "docs": dict,
        "roster": dict,
    }
    for key, kind in required.items():
        if not isinstance(data.get(key), kind):
            errors.append(f"settings.{key}: missing or wrong type")
    docs = data.get("docs") or {}
    if not isinstance(docs.get("base_url"), str):
        errors.append("settings.docs.base_url: must be string")
    roster = data.get("roster") or {}
    if not isinstance(roster.get("batch_size"), int):
        errors.append("settings.roster.batch_size: must be int")
    if not isinstance(roster.get("max_facts_per_issue"), int):
        errors.append("settings.roster.max_facts_per_issue: must be int")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: python -m tests.validate_schema <profiles.json> <settings.json>")
        return 2
    profiles_errors = validate_profiles_file(Path(argv[1]))
    settings_errors = validate_settings_file(Path(argv[2]))
    for e in profiles_errors + settings_errors:
        print(f"FAIL: {e}")
    if profiles_errors or settings_errors:
        return 1
    print("OK — schema valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 5.5: Write test runner**

`tests/test_validate_schema.py`:

```python
"""Round-trip tests for the schema validator."""
import sys
from pathlib import Path

from tests.validate_schema import validate_profiles_file, validate_settings_file

ROOT = Path(__file__).parent / "fixtures"


def main() -> int:
    failures: list[str] = []

    errs = validate_profiles_file(ROOT / "profiles_v05.json")
    if errs:
        failures.append(f"profiles_v05.json should validate, got: {errs}")

    errs = validate_profiles_file(ROOT / "profiles_legacy.json")
    if errs:
        failures.append(f"profiles_legacy.json should validate (legacy tolerated), got: {errs}")

    errs = validate_settings_file(ROOT / "settings_v05.json")
    if errs:
        failures.append(f"settings_v05.json should validate, got: {errs}")

    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("OK — validator round-trip passes for v0.5 + legacy fixtures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5.6: Run validator tests**

```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && python -m tests.test_validate_schema
```

Expected: `OK — validator round-trip passes for v0.5 + legacy fixtures`.

- [ ] **Step 5.7: Run validator on a v0.5 fixture pair end-to-end**

```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && \
python -m tests.validate_schema tests/fixtures/profiles_v05.json tests/fixtures/settings_v05.json
```

Expected: `OK — schema valid`.

- [ ] **Step 5.8: Stage**

```bash
git add tests/validate_schema.py tests/fixtures/profiles_v05.json tests/fixtures/profiles_legacy.json tests/fixtures/settings_v05.json tests/test_validate_schema.py
```

---

### Task 6: Extend `/bigeye-config` with `hints` subcommands + name resolution

**Files:**
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-config/SKILL.md`

- [ ] **Step 6.1: Add subcommand rows to the Arguments table**

In the `## Arguments` section, append rows after the `verify` row:

```markdown
| `hints add` | Author a custom hint via NL → compile → confirm → save (uses `references/hints.md`) |
| `hints list [<profile>]` | List custom hints for the given (or active) profile |
| `hints edit <index>` | Edit hint at index (re-runs compile prompt with prior raw pre-filled) |
| `hints delete <index>` | Remove hint at index |
| `virtual-tables add <name>` | MCP-resolve a virtual table by name → save `{id, name}` to active profile |
| `virtual-tables list` | List virtual tables on the active profile |
| `virtual-tables delete <name-or-id>` | Remove a virtual table from the active profile |
```

- [ ] **Step 6.2: Update the schema example**

Replace the existing schema block under `**`~/.claude/bigeye-plugin/profiles.json`** — plugin-owned…` with:

```markdown
**Schema (v0.5):**

```json
{
  "active_profile": "prod",
  "profiles": {
    "prod": {
      "workspace_id": 42,
      "scope": {
        "data_sources":   [{"id": 17, "name": "warehouse_prod"}],
        "schemas":        [],
        "tables":         [{"id": 901, "name": "orders_main"}],
        "virtual_tables": []
      },
      "monitored_rules": [{"id": 1, "name": "freshness"}],
      "custom_hints": []
    }
  }
}
```

`active_profile` (formerly `default_profile`) keeps backward-compatible read; new writes use `active_profile`.
```

- [ ] **Step 6.3: Add a "Hints" subsection**

After `## Settings File`, insert:

````markdown
## Custom Hints

Hint compile + storage are documented in `skills/bigeye/references/hints.md`. This skill is the only writer for `custom_hints`.

### Subcommand: `hints add`

1. Hard-fail if `MCP_AVAILABLE=false` (per preamble Step 7.E).
2. Ask: `Hint scope? (table / monitor)`.
3. Ask for the target name. Resolve via MCP (`mcp__bigeye__list_tables` for tables; `mcp__bigeye__list_table_metrics` for monitors). On ambiguity → list candidates with IDs, user picks.
4. Ask: `Describe the hint in plain text.`
5. Run the compile prompt from `references/hints.md`. If ambiguous → ask follow-up. Refuse to save without a compiled shape.
6. Show the compiled JSON. Ask: `Save this hint? (y/n)`.
7. On `y`: append `{scope, target_id, target_name, raw, compiled, created_at: now()}` to `profiles[<active>].custom_hints` and write atomically.
8. On `n`: discard, ask `Try again? (y/n)`. On `y` → restart at Step 4. On `n` → exit.

### Subcommand: `hints list [<profile>]`

Print a numbered table:

```
# | Scope   | Target            | Type             | Raw
1 | table   | orders            | noise_threshold  | ignore deltas under 2% on row_count
2 | monitor | metric#4421       | expected_pattern | weekend spikes are expected
```

If the profile has no hints → `No custom hints on profile {name}. Add via /bigeye-config hints add.`

### Subcommand: `hints edit <index>`

1. Load profile. Validate index is in range.
2. Show the existing compiled form.
3. Re-run `hints add` flow with the existing `raw` pre-filled (user can edit before compile).
4. Replace at the same index. Write atomically.

### Subcommand: `hints delete <index>`

1. Load profile, validate index.
2. Confirm: `Delete hint #{index}: {raw}? (y/n)`.
3. On `y` → splice out, write atomically.
````

- [ ] **Step 6.4: Add a "Virtual tables" subsection**

After the Custom Hints subsection, insert:

````markdown
## Virtual Tables

### Subcommand: `virtual-tables add <name>`

1. Hard-fail if `MCP_AVAILABLE=false`.
2. Search via `mcp__bigeye__search_lineage_nodes` (or equivalent) filtered to virtual tables in the workspace. On ambiguity → list candidates with IDs, user picks.
3. If `name` matches a regular table only → reject with: `\`{name}\` is a regular table, not a virtual table. Add it via the wizard's table step instead.`
4. Append `{id, name}` to `scope.virtual_tables`. Write atomically.

### Subcommand: `virtual-tables list`

Print:

```
# | ID  | Name
1 | 55  | active_users_30d
```

### Subcommand: `virtual-tables delete <name-or-id>`

1. Resolve to one entry. Ambiguity → ask which.
2. Splice out. Write atomically.
````

- [ ] **Step 6.5: Replace `## Wizard Flow` to use the v0.5 schema and resolve names → IDs**

Replace the entire `## Wizard Flow` section with:

````markdown
## Wizard Flow

Hard-fail if `MCP_AVAILABLE=false`. (The wizard depends on MCP for name → ID resolution.)

Ask one question at a time. Show the running summary after each answer.

1. **Workspace ID.** Ask: `What's your BigEye workspace_id? (integer)`. Validate integer; confirm reachability via `mcp__bigeye__list_data_sources`.
2. **Data sources.** Ask: `Filter by data source? (y/n)`. On yes: list available via MCP; user picks indices. Save resolved `[{id, name}]` to `scope.data_sources`.
3. **Schemas.** Ask: `Filter by schema? (y/n)`. On yes: per data source, list available via MCP; user picks. Save `[{id, name}]`.
4. **Tables.** Ask: `Filter by tables? (y/n)`. On yes: ask for one name per line. For each: MCP-resolve. On ambiguity → list candidates with IDs, user picks. On no match → warn, skip. Save `[{id, name}]` in `scope.tables`.
5. **Virtual tables.** Ask: `Include virtual tables? (y/n)`. Same flow as tables but filtered to virtual-table type.
6. **Monitored rules.** Ask: `Restrict to specific dimensions/rules? (y/n)`. On yes: list dimensions via `mcp__bigeye__list_dimensions`; user picks. Save `[{id, name}]`.
7. **Custom hints.** Skip in the wizard — hints are added later via `/bigeye-config hints add` once tables exist.
8. **Summary and confirmation.** Show the resolved profile JSON (truncated to first 5 entries per array). Ask `Save this profile? (y/n)`.

On `y` proceed to the caller's write step.
````

- [ ] **Step 6.6: Demote CLI references**

Find the line beginning `**`~/.bigeye/config.ini`** — plugin writes the section…`. Replace its surrounding paragraph with:

```markdown
The plugin no longer requires the BigEye CLI for the v0.5 user-facing pillars. The CLI section in `~/.bigeye/config.ini` is **only** written when the user opts into legacy CLI integration (kept for hidden skills). When the wizard finishes, ask: `Also configure ~/.bigeye/config.ini for legacy CLI use? (y/n, default n)`. Default `n` skips the file write entirely.
```

- [ ] **Step 6.7: Stage**

```bash
git add skills/bigeye-config/SKILL.md
```

---

## Phase 3 — Roster skill (new)

### Task 7: Create roster reference (`roster.md`)

Shared facts/recommendation/action handlers used by the new `bigeye-roster` skill. Splits the procedural logic out of `SKILL.md` so the SKILL.md stays declarative.

**Files:**
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/roster.md`

- [ ] **Step 7.1: Create reference file**

````markdown
# Roster — facts, recommendation, action handlers

## Fact gathering (per issue)

For each issue, gather up to `roster.max_facts_per_issue` (default 6) facts:

| Fact | Source | Cost |
|---|---|---|
| `current_metric` | `mcp__bigeye__get_issue` | 1 call |
| `metric_trend` (last N runs, default 30 days) | `mcp__bigeye__list_table_metrics` filtered to monitor | 1 call |
| `recurrence_count` (last 90d for same monitor) | `mcp__bigeye__search_issues(monitor_id=…)` | 1 call |
| `matching_hints` | local `profiles[active].custom_hints` filtered by scope+target | 0 calls |
| `profile_drift` | `mcp__bigeye__get_table_profile` delta vs prior snapshot | 1 call (cache 24h per table) |

Skip any fact whose source returns an MCP error; mark with `(unavailable)` in the rendered fact list. Do not hard-fail the loop.

## Recommendation derivation

Given the gathered facts, choose ONE primary recommendation. Tiebreak in this order:

1. **`close — metric recovered`** if `current_metric` is back under threshold AND stable for ≥2 consecutive runs in `metric_trend`.
2. **`close — within user noise floor`** if any `matching_hints` is `noise_threshold` AND the issue's current delta % ≤ `delta_pct_max`.
3. **`improve`** if `recurrence_count >= 5` AND deltas have a small consistent magnitude (`|delta| < 10%` across the trend).
4. **`ticket`** if `profile_drift` is detected (column null-rate shift > 5pp, or row-count shift > 25%).
5. **`investigate`** otherwise — describes the facts, recommends manual review.

## Render template

```
[Issue #{id} — {table}.{column} {dimension}, severity {sev}]
Facts:
  • {fact 1}
  • {fact 2}
  ...
Recommendation: {one sentence}
                {one-line "why" referencing the rule above}
                Source: {doc URL — see grounding.md}
Action? [c]lose  [f]laky-note  [t]icket  [i]mprove  [h]int  [s]kip
```

Each line under `Facts:` is one short clause. No nested bullets. Cap each fact at 80 columns.

## Action handlers

| Key | Handler |
|---|---|
| `c` | Ask for one-line reason. Call `mcp__bigeye__update_issue(issue_id, status=CLOSED, reason=<user>)`. Append `{issue_id, action:"close", reason, ts}` to `state.json`. |
| `f` | Ask for one-line note. Call `mcp__bigeye__update_issue(issue_id, status=ACKNOWLEDGED, note=<user prefixed with "[flaky] ">)`. Append `{action:"flaky"}` to `state.json`. |
| `t` | Render markdown ticket via the existing `bigeye-ticket` skill (via Skill tool, passing `<issue_id>`). Print result to terminal. Append `{action:"ticket"}` to `state.json`. Continue. |
| `i` | Print: `Run /bigeye-improve <monitor_id> to deep-analyze this monitor.` Append `{action:"improve_suggested"}`. Continue. |
| `h` | Trigger `/bigeye-config hints add` flow (Skill tool) with scope/target pre-filled to this issue's monitor or table. After save, re-evaluate facts for the current issue and re-render. Treat re-rendered prompt as a fresh action choice. |
| `s` | Append `{action:"skip"}`. Continue to next issue. |

If MCP write fails for `c` or `f`: print the error block (Error/Fix/Why), keep issue open, ask `Try again, skip, or stop? (r/s/x)`.

## Pacing

Process in batches of `roster.batch_size`. After each batch:

```
Batch {N} complete. {x} closed, {y} flaky-noted, {z} tickets, {q} improvements suggested, {s} skipped.
Continue? (y/n)
```

`n` → end-of-pass summary.

## Resumability

Each action appended to `state.json` under `state.issues[<id>].actions`. On the next `/bigeye-roster` invocation, skip any issue whose newest `action` is in `{close, flaky, skip}` and whose timestamp is within the last 24 hours. Override with `--include-actioned`.
````

- [ ] **Step 7.2: Stage**

```bash
git add skills/bigeye/references/roster.md
```

---

### Task 8: Create `/bigeye-roster` skill

**Files:**
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-roster/SKILL.md`

- [ ] **Step 8.1: Write SKILL.md**

````markdown
---
name: bigeye-roster
description: Use when the user wants to walk today's BigEye issues — daily routine that gathers facts per issue, presents a recommendation, and lets the user pick the action. Advisory only; the user decides every action.
user-invocable: true
---

# BigEye Daily Roster Routine

What it does: iterates open issues in the active profile's scope. Per issue: gathers facts, derives a recommendation, prints a short rendering, asks the user to pick an action. Advisory — never auto-closes anything.

Follow `skills/bigeye/references/preamble.md` Steps 1–7 first. Hard-fail per Step 7.E when MCP is unreachable. Facts/recommendation/action handlers live in `skills/bigeye/references/roster.md`. Output shape lives in `skills/bigeye/references/output.md`.

## Arguments

| Invocation | Behavior |
|---|---|
| (empty) | Walk active profile's open issues |
| `--include-actioned` | Include issues actioned in the last 24h (otherwise skipped) |
| `--limit <N>` | Stop after N issues |
| `--batch <N>` | Override `settings.roster.batch_size` |
| `--profile <name>` | Use named profile for this run |

Global flags from `output.md` apply.

## Procedure

1. Follow `preamble.md` Steps 1–7. Hard-fail per Step 7.E when MCP is off — print the reconnect block and stop.
2. Build the issue list:
   - `mcp__bigeye__list_issues` with profile-derived parameter map (workspace_id, data_source_ids, table_ids, schema_names, dimension_ids from `monitored_rules`).
   - Filter to `status in {NEW, ACKNOWLEDGED}`.
   - Apply resumability filter from `roster.md` unless `--include-actioned`.
   - Order by `(severity desc, opened_at asc)`.
3. Loop in batches of `settings.roster.batch_size` (overridden by `--batch`):
   - For each issue, gather facts per `roster.md` §"Fact gathering". Gather in parallel where MCP supports it.
   - Derive recommendation per `roster.md` §"Recommendation derivation".
   - Render per `roster.md` §"Render template". Cite a docs URL for the dimension involved (delegate to `bigeye-docs-grounding`).
   - Wait for user action input. Run the matching handler from `roster.md` §"Action handlers".
4. After each batch, print the batch summary line and ask `Continue? (y/n)`.
5. End-of-pass summary:
   ```
   Roster complete — {N} issues reviewed.
     close: {x}    flaky-note: {y}    ticket: {z}
     improve suggested: {q}    hint added: {h}    skip: {s}
   ```
6. Footer:
   ```
   Next: /bigeye-roster --include-actioned     (re-walk including recently-actioned)
   More: /bigeye-improve <monitor_id>  ·  /bigeye-coverage <table>  ·  /bigeye-config hints list
   ```

## State persistence

Per action: append `{skill:"bigeye-roster", action:"<key>", at:<iso8601>, reason:<optional>}` to `state.json.issues[<id>].actions`. Update `state.last_workflow = "bigeye-roster"`. Run pruning per preamble Step 8.C.

## Errors

- MCP unreachable at start → reconnect block (preamble 7.E) and stop.
- MCP fails mid-loop on a single fact → mark `(unavailable)`; continue.
- MCP fails mid-loop on an action write → Error/Fix/Why block; ask retry/skip/stop.
- User answers an unknown key in the action prompt → repeat the menu once; on second unknown → skip.
````

- [ ] **Step 8.2: Stage**

```bash
git add skills/bigeye-roster/SKILL.md
```

---

## Phase 4 — Improve skill: single-monitor mode

### Task 9: Create `improve-single.md` reference

**Files:**
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/improve-single.md`

- [ ] **Step 9.1: Write file**

````markdown
# Improve — single-monitor procedure

Used by `/bigeye-improve <monitor_id>`.

## Inputs

- `monitor_id` (int) — required
- profile (active or `--profile <name>`)
- custom hints scoped to the monitor or its table

## Procedure

1. Resolve monitor: `mcp__bigeye__get_table_metrics` filtered to `monitor_id` to fetch metric type, current threshold, table, column.
2. Gather profile + history:
   - `mcp__bigeye__get_table_profile(table_id, columns=[<col>])` — column distribution / null rate / cardinality / format samples / numeric range.
   - `mcp__bigeye__list_table_metrics(table_id)` filtered to `monitor_id` — last 30d runs.
   - Read `custom_hints` filtered by `(scope=monitor AND target_id=<monitor_id>)` OR `(scope=table AND target_id=<table_id>)`.
3. Generate candidate change. For threshold metrics, propose new bounds based on observed distribution + history. For regex/categorical, propose a tightened pattern grounded in actual values.
4. SQL refinement loop (max 3 iterations):
   1. Emit candidate validation SQL: a SELECT that would have flagged a row if the proposed threshold were active during the last 30d.
   2. Run the SQL via `mcp__bigeye__create_metric` dry-run mode if available, else fall back to documenting the SQL for the user to inspect.
   3. Count FP/FN against the existing closed-issues record for the monitor (`mcp__bigeye__search_issues(monitor_id, status=CLOSED)`).
   4. Adjust candidate to reduce FP+FN. Stop on convergence (FP+FN unchanged) or after iteration 3.
5. Render proposal — see template below. Read-only — never call create/update.

## Render template

```
{scope pill}
## Single-Monitor Improvement — Metric #{monitor_id}

Table:    {schema}.{table_name}
Column:   {column}
Type:     {metric_type}
Current:  {current_threshold_summary}
Proposal: {new_threshold_summary}

Why:
  • {one sentence per supporting fact, max 4 bullets}

Validation SQL (last 30d):
  ```sql
  {sql block, ≤ 25 lines}
  ```
  At proposed threshold: {FP} false positives, {FN} false negatives.
  At current threshold:  {FP_now} false positives, {FN_now} false negatives.

Custom hints applied:
  {bullet per matching hint, "(none)" if empty}

Source: {doc URL for this metric type}

Deploy:
  /bigeye-deploy monitor {monitor_id} --threshold {new_threshold_args}
```

## Errors

- `monitor_id` not found → `Monitor #{id} not found in workspace. Fix: /bigeye-improve <table_name> to list monitors on a table.`
- Profile fetch partial fail → annotate the affected row `(profile unavailable)`. Continue.
- Validation SQL fails to run → emit the SQL anyway with `(SQL run failed — please verify manually)`. Skip FP/FN counts.
````

- [ ] **Step 9.2: Stage**

```bash
git add skills/bigeye/references/improve-single.md
```

---

### Task 10: Wire single-monitor mode into `bigeye-improve`

**Files:**
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-improve/SKILL.md`

- [ ] **Step 10.1: Add the `<monitor_id>` row to the Arguments table**

Replace the `metric <metric_id>` row with:

```markdown
| `<monitor_id>` | Single-monitor improve mode (integer) — runs the procedure in `references/improve-single.md` | `/bigeye-improve 4421` |
| `metric <metric_id>` | (Legacy alias for `<monitor_id>` — kept for older docs/scripts) | `/bigeye-improve metric 17321` |
```

- [ ] **Step 10.2: Add a single-monitor branch at the top of `## Procedure`**

Insert as the new Step 1 (renumber the rest accordingly):

````markdown
1. **Argument detection:**
   - If `$ARGUMENTS` first non-flag token is a positive integer (or the literal `metric <int>`), treat as **single-monitor mode**:
     - Hard-fail per preamble 7.E if MCP is off.
     - Run the procedure in `skills/bigeye/references/improve-single.md` and stop.
   - Otherwise continue with the existing table-mode flow.
````

- [ ] **Step 10.3: Add hard-fail when MCP is off (single-monitor mode)**

Inside the new Step 1's "single-monitor mode" sub-step, append:

```markdown
   - Print the reconnect block from preamble 7.E and stop.
```

- [ ] **Step 10.4: Stage**

```bash
git add skills/bigeye-improve/SKILL.md
```

---

## Phase 5 — Coverage skill: interactive batch proposal

### Task 11: Create `coverage-interactive.md` reference

**Files:**
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/coverage-interactive.md`

- [ ] **Step 11.1: Write file**

````markdown
# Coverage — interactive batch proposal

Used by `/bigeye-coverage <table>` (v0.5).

## Inputs

- table — required (resolve to `table_id` via MCP; ambiguity → user picks)
- active profile + `monitored_rules` (limits which dimensions are considered)

## Procedure

1. Resolve target table → `table_id`.
2. `mcp__bigeye__get_table_profile(table_id)` → per-column profile (null %, distinct count, cardinality, format samples, numeric / length stats).
3. `mcp__bigeye__get_table_dimension_coverage(table_id)` → existing monitor coverage.
4. Identify uncovered or weakly-covered columns. Filter to dimensions in `profile.monitored_rules`. Order: PK → FK → indexed → numeric → categorical → text.
5. Iterate columns in batches of 3:
   1. Show the auto-detected profile for the column:
      ```
      Column: {name}
        type:        {data_type}
        null_pct:    {x}%
        distinct:    {n} ({x}% of rows)
        format hint: {regex matched on >95% of samples, or "—"}
        samples:     [{up to 5}]
      ```
   2. Ask: `What does this column hold?` Provide the auto-guess summary + accepted answer forms:
      - `confirm` (auto-guess is correct)
      - `<free text>` describing the data (e.g. `work emails @company.com only`)
      - `skip` (no monitor for this column)
   3. Map (auto-guess + user constraint + profile) → fitted monitor candidates:
      - REGEX_MATCH if the user describes a format pattern.
      - COMPLETENESS if `null_pct > 0` and user confirms non-nullable.
      - UNIQUENESS if user confirms unique.
      - FRESHNESS if column is timestamp + user confirms it tracks last update.
      - VALUE_RANGE if numeric + user gives bounds.
   4. Render fitted candidates with reasoning + doc URL citation. Ask: `Queue which? (comma list / all / none)`.
   5. Append picked items to the in-memory queue.
6. After all columns processed (or user types `stop`), render the bulk deploy block:
   ```
   Queued monitors for {schema}.{table_name}:
     1. {dimension} on {column}        — reasoning: {one sentence}
     2. ...
   Deploy: /bigeye-deploy gaps {table} --queued
   ```
7. Read-only output. User runs deploy separately.

## Resumability

Per-column queue + last-processed column saved to `state.tables[<fq>].coverage_queue`. `/bigeye-coverage` no-arg resumes from the next unprocessed column.

## Errors

- Column profile fetch fails → mark `(profile unavailable for {column})`. Continue with the rest of the batch.
- User types unparseable answer twice → skip the column with `(skipped — unparsed input)`.
````

- [ ] **Step 11.2: Stage**

```bash
git add skills/bigeye/references/coverage-interactive.md
```

---

### Task 12: Rewrite `/bigeye-coverage` for interactive mode

**Files:**
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-coverage/SKILL.md`

- [ ] **Step 12.1: Replace the whole `## Procedure` section**

Replace `## Procedure` with:

````markdown
## Procedure

1. Hard-fail per preamble Step 7.E if MCP is off.
2. Follow preamble Steps 1–7.
3. Resolve target table → `table_id`. Argument given → use it (ambiguity → user picks). No argument: use `state.json.last_table` if set, else ask.
4. Run the procedure in `skills/bigeye/references/coverage-interactive.md`.
5. Footer:
   ```
   Next: /bigeye-deploy gaps {table} --queued     ({queued_count} queued monitors)
   More: /bigeye-improve <monitor_id>  ·  /bigeye-roster
   ```
````

- [ ] **Step 12.2: Update the Arguments table**

Replace the Arguments table with:

```markdown
| Invocation | Purpose |
|---|---|
| `<table>` | Run interactive coverage on the named table |
| (no arg) | Resume `state.json.last_table` if set, else ask which table |
| `--profile <name>` | Run with a non-active profile |
```

- [ ] **Step 12.3: Drop the `## Errors` section's CLI references**

Replace `## Errors` with:

```markdown
## Errors

- MCP unreachable → preamble 7.E reconnect block. Stop.
- Table not found → `Table {name} not found in workspace. Fix: /bigeye-config show to confirm scope.`
- Per-column profile fetch fails → annotate `(profile unavailable for {column})` and continue.
```

- [ ] **Step 12.4: Stage**

```bash
git add skills/bigeye-coverage/SKILL.md
```

---

## Phase 6 — Doc grounding (ambient)

### Task 13: Create `grounding.md` reference

**Files:**
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/grounding.md`

- [ ] **Step 13.1: Write file**

````markdown
# Doc grounding

The plugin grounds explanations of BigEye monitor types, dimensions, threshold semantics, and coverage concepts in the BigEye docs site. Citation-first.

## URL conventions

Base URL: `settings.docs.base_url` (default `https://docs.bigeye.com`).

| Topic | Path hint |
|---|---|
| Freshness dimension | `/dimensions/freshness` |
| Volume / row-count dimension | `/dimensions/volume` |
| Uniqueness dimension | `/dimensions/uniqueness` |
| Completeness / null dimension | `/dimensions/completeness` |
| Regex / format monitor | `/monitor-types/regex-match` |
| Range monitor | `/monitor-types/value-range` |
| Profile-based monitors | `/monitors/profile-based` |

When the exact path is unknown: WebFetch the base URL, follow the first matching link in nav, fall back to the search page (`/search?q={topic}`).

## Citation format

Always inline. Per render:

```
... explanation ...
Source: {url}
```

For multi-bullet renders, cite per bullet only when bullets reference different docs pages. Otherwise a single trailing `Source: …` line covers the section.

## Failure mode

WebFetch fails (timeout, 4xx, 5xx) → answer best-effort and append:

```
(docs unreachable — no citation)
```

Never block the parent skill.
````

- [ ] **Step 13.2: Stage**

```bash
git add skills/bigeye/references/grounding.md
```

---

### Task 14: Create `bigeye-docs-grounding` skill

**Files:**
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-docs-grounding/SKILL.md`

- [ ] **Step 14.1: Write SKILL.md**

````markdown
---
name: bigeye-docs-grounding
description: Use whenever you are about to explain a BigEye monitor type, dimension, threshold semantic, coverage concept, or any BigEye behavior to the user. Fetches the relevant page from the BigEye docs site and cites the URL inline. Auto-invoked by other BigEye skills (roster / improve / coverage / config) when their renders explain a concept.
user-invocable: false
---

# BigEye Docs Grounding (ambient)

Not a slash command. Invoked transparently when another BigEye skill (or a free-form user question) is about to explain a BigEye concept.

Follow `skills/bigeye/references/grounding.md` for URL conventions and citation format.

## Procedure

1. Read `settings.docs.base_url` (default `https://docs.bigeye.com`). If `settings.json` is missing, fall back to the default without writing.
2. Build a candidate URL from the topic using the path hints in `references/grounding.md`. Always fall back to a single search-page URL if the topic isn't in the table.
3. WebFetch the candidate URL.
4. Extract the heading + first useful paragraph relevant to the topic. Trim to ≤ 250 words.
5. Return the answer in the parent's voice (never insert "I fetched docs" framing) — caller renders. Always end with:
   ```
   Source: {url}
   ```
6. WebFetch failure → return best-effort knowledge and append:
   ```
   (docs unreachable — no citation)
   ```

## Caching

No local cache. WebFetch's per-request cache is sufficient. If the same topic is grounded multiple times in one session, allow re-fetch.

## Errors

Never raises. Failures degrade to "(docs unreachable — no citation)".
````

- [ ] **Step 14.2: Stage**

```bash
git add skills/bigeye-docs-grounding/SKILL.md
```

---

### Task 15: Wire grounding into roster / improve / coverage outputs

The render templates in `roster.md`, `improve-single.md`, and `coverage-interactive.md` already include a `Source: …` line per recommendation. Make sure each calling skill says "delegate to `bigeye-docs-grounding`" rather than fabricating URLs.

**Files:**
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/roster.md`
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/improve-single.md`
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/coverage-interactive.md`

- [ ] **Step 15.1: Add a one-line note to `roster.md` under "Render template"**

Append after the render-template code block:

```markdown
The `Source:` line is filled by delegating to `bigeye-docs-grounding` with the issue's dimension as the topic. Do not fabricate URLs locally.
```

- [ ] **Step 15.2: Add the same note to `improve-single.md`**

Append after the render-template code block:

```markdown
The `Source:` line is filled by delegating to `bigeye-docs-grounding` with the metric type as the topic.
```

- [ ] **Step 15.3: Add the same note to `coverage-interactive.md`**

Append after Step 5.4 in the Procedure:

```markdown
Each fitted candidate's reasoning ends with a `Source: …` line. Delegate URL resolution to `bigeye-docs-grounding` with the candidate dimension as the topic.
```

- [ ] **Step 15.4: Stage**

```bash
git add skills/bigeye/references/roster.md skills/bigeye/references/improve-single.md skills/bigeye/references/coverage-interactive.md
```

---

## Phase 7 — Visibility cleanup

### Task 16: Trim hidden-skill descriptions

For each hidden skill, rewrite ONLY the frontmatter `description:` line. Keep `user-invocable: true` so direct slash invocations still work; the description rewrite removes them from the model's auto-discovery surface.

**Files:**
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/SKILL.md`
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-rca/SKILL.md`
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-today/SKILL.md`
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-table/SKILL.md`
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-triage/SKILL.md`
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-incidents/SKILL.md`
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-ticket/SKILL.md`
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-deploy/SKILL.md`

- [ ] **Step 16.1: `skills/bigeye/SKILL.md` — replace `description:`**

Replace the existing description line with:

```yaml
description: Internal — invoked only when explicitly typed as `/bigeye`. Do not auto-suggest. The user-facing surface in v0.5 is `/bigeye-roster`, `/bigeye-improve`, `/bigeye-coverage`, `/bigeye-config`.
```

- [ ] **Step 16.2: `skills/bigeye-rca/SKILL.md`**

```yaml
description: Internal — root-cause-analysis helper invoked only when explicitly typed as `/bigeye-rca`. Do not auto-suggest. Roster recommends `improve` or `ticket` instead.
```

- [ ] **Step 16.3: `skills/bigeye-today/SKILL.md`**

```yaml
description: Internal — superseded by `/bigeye-roster` for the daily flow. Callable directly when explicitly typed as `/bigeye-today`. Do not auto-suggest.
```

- [ ] **Step 16.4: `skills/bigeye-table/SKILL.md`**

```yaml
description: Internal — table audit helper invoked only when explicitly typed as `/bigeye-table`. Do not auto-suggest. Use `/bigeye-coverage <table>` and `/bigeye-improve <monitor_id>` instead.
```

- [ ] **Step 16.5: `skills/bigeye-triage/SKILL.md`**

```yaml
description: Internal — invoked only when explicitly typed as `/bigeye-triage`. Do not auto-suggest. Use `/bigeye-roster` instead.
```

- [ ] **Step 16.6: `skills/bigeye-incidents/SKILL.md`**

```yaml
description: Internal — incident grouping helper invoked only when explicitly typed as `/bigeye-incidents`. Do not auto-suggest.
```

- [ ] **Step 16.7: `skills/bigeye-ticket/SKILL.md`**

```yaml
description: Internal — markdown ticket renderer invoked by `/bigeye-roster` action `t` or directly when explicitly typed as `/bigeye-ticket <issue>`. Do not auto-suggest.
```

- [ ] **Step 16.8: `skills/bigeye-deploy/SKILL.md`**

```yaml
description: Internal — monitor deployer invoked only when explicitly typed as `/bigeye-deploy`. Do not auto-suggest. `/bigeye-improve` and `/bigeye-coverage` produce read-only proposals; user runs deploy separately.
```

- [ ] **Step 16.9: Stage**

```bash
git add skills/bigeye/SKILL.md skills/bigeye-rca/SKILL.md skills/bigeye-today/SKILL.md skills/bigeye-table/SKILL.md skills/bigeye-triage/SKILL.md skills/bigeye-incidents/SKILL.md skills/bigeye-ticket/SKILL.md skills/bigeye-deploy/SKILL.md
```

---

### Task 17: Rewrite `README.md`

**Files:**
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/README.md`

- [ ] **Step 17.1: Replace the entire README contents**

Write:

````markdown
# BigEye Data Observability Plugin

A Claude Code plugin focused on three workflows: a daily roster routine over open BigEye issues, single-monitor improve, and an interactive batch coverage proposal. Plus an ambient docs-grounding layer — every monitor / dimension / threshold explanation is cited back to the BigEye docs site.

## What's new in 0.5.0

- **Three pillars only on the user surface.** `/bigeye-roster`, `/bigeye-improve <monitor_id>`, `/bigeye-coverage <table>`.
- **`/bigeye-roster` (new).** Daily routine: walk open issues, see facts + recommendation per issue, pick close / flaky-note / ticket / improve / hint / skip. Advisory only — never auto-closes.
- **Custom hints.** Author per-table or per-monitor advisory rules in plain text via `/bigeye-config hints add`. Plugin compiles to a structured predicate before saving.
- **Interactive coverage.** `/bigeye-coverage <table>` walks columns one at a time, shows the auto-detected profile, asks what the column actually holds, and proposes monitors that fit.
- **MCP-only.** The BigEye CLI is no longer required for the user-facing pillars. CLI-based hidden skills remain on disk and callable.
- **Doc grounding.** Every monitor / dimension explanation cites the matching BigEye docs URL.

## Requirements

- Claude Code with plugin support
- **BigEye MCP server** authenticated against your workspace — see [`bigeye-mcp-install.md`](bigeye-mcp-install.md)

(Slack MCP optional, only used by the legacy morning-report agent.)

## Installation

```bash
/plugin marketplace add andriikoziichuk/bigeye-plugin
/plugin install bigeye-plugin@andriikoziichuk-bigeye-plugin
```

After install: `/bigeye-config init` to bind your workspace and scope.

## Commands

| Command | Description |
|---|---|
| `/bigeye-roster` | Daily routine — walk open issues, act on each |
| `/bigeye-improve <monitor_id>` | Single-monitor improve — read-only proposal grounded in profile data and validated with SQL |
| `/bigeye-coverage <table>` | Interactive batch proposal — per-column conversation, fitted monitors |
| `/bigeye-config [subcmd]` | Profiles + custom hints + virtual tables + settings |

## Daily flow

```
/bigeye-roster                      # walk issues, advisory recs per issue
   ↓
[i]mprove on a flagged issue        # → /bigeye-improve <monitor_id>
[c]lose / [f]laky-note inline       # MCP write per action
[h]int adds advisory rule to profile
   ↓
/bigeye-coverage <table>            # find gaps, propose monitors
   ↓
/bigeye-deploy …                    # apply (callable, hidden surface)
```

## Configuration

**Profiles** (`~/.claude/bigeye-plugin/profiles.json`) — workspace + scope (data sources / schemas / tables / virtual tables) + monitored rules + custom hints. Owned by `/bigeye-config`. Per-invocation overrides: `--profile <name>`, `--no-scope`, `--workspace <id>`.

**Settings** (`~/.claude/bigeye-plugin/settings.json`) — Slack channel (legacy), severity thresholds (legacy), `docs.base_url`, `roster.batch_size`, `roster.max_facts_per_issue`. Edit via `/bigeye-config settings show` / `settings edit <key> <value>`.

**Activity log** (`~/.claude/bigeye-plugin/state.json`) — append-only, LRU-pruned. Powers roster resumability and the `(no-arg)` resume on coverage / improve.

## Without MCP

The user-facing pillars hard-fail with:

```
MCP unreachable. Try:
  1. /mcp reconnect bigeye
  2. Retry the command
If still failing: see bigeye-mcp-install.md
```

Run `/bigeye-config verify` to see exactly what's reachable.
````

- [ ] **Step 17.2: Stage**

```bash
git add README.md
```

---

### Task 18: Trim CLI fallback paths in shared references

`preamble.md` and `output.md` reference CLI fallback flows that are no longer reachable from the v0.5 user surface. Trim them — leave the CLI fallback notes only inside hidden-skill SKILL.md files (so they still work when those skills are invoked directly).

**Files:**
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/preamble.md`
- Modify: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/output.md`

- [ ] **Step 18.1: Audit and prune `preamble.md`**

Find every paragraph that explicitly names CLI invocations (`bigeye -w …`, `~/.bigeye/credentials`, `bigeye configure list`). Move each into a single new section at the bottom of the file titled:

```markdown
## CLI fallback (legacy hidden skills only)

These steps apply ONLY when a hidden skill is invoked directly. The v0.5 user-facing pillars are MCP-only — they never reach this section.

(insert the CLI-related paragraphs here, verbatim)
```

Then in earlier steps, replace the inline CLI guidance with a single line: `For CLI fallback (hidden skills only) see "CLI fallback" at the bottom of this file.`

- [ ] **Step 18.2: Verify no stray CLI mentions remain in the v0.5 sections**

```bash
grep -n "bigeye -w\|bigeye configure\|~/.bigeye/credentials" skills/bigeye/references/preamble.md
```

Expected: every match line number is past the new "CLI fallback" header (use a quick read of the file to confirm).

- [ ] **Step 18.3: Update `output.md`**

Find any sentence that says "the CLI is the primary transport" or equivalent. Replace with: `MCP is the primary transport for the v0.5 user-facing pillars (`bigeye-roster`, `bigeye-improve`, `bigeye-coverage`). CLI is invoked only by hidden skills.`

- [ ] **Step 18.4: Stage**

```bash
git add skills/bigeye/references/preamble.md skills/bigeye/references/output.md
```

---

## Phase 8 — Manual test artifacts

### Task 19: Skill discovery checklist

**Files:**
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/tests/skill-discovery.md`

- [ ] **Step 19.1: Write checklist**

````markdown
# Skill discovery checklist (manual)

Run at session start by typing each phrase and checking which skill auto-invokes. Phrases marked **must auto-invoke** the listed skill.

| Phrase | Should auto-invoke |
|---|---|
| "let's go through today's issues" | `bigeye-roster` |
| "walk me through open issues" | `bigeye-roster` |
| "improve monitor 4421" | `bigeye-improve` |
| "tighten the threshold on monitor 4421" | `bigeye-improve` |
| "what gaps does table orders have" | `bigeye-coverage` |
| "find missing monitors on orders" | `bigeye-coverage` |
| "add a hint to my profile" | `bigeye-config` |
| "switch profile to staging" | `bigeye-config` |
| "how does freshness work in BigEye" | `bigeye-docs-grounding` (ambient — confirm citation appears) |
| "what's the difference between completeness and uniqueness" | `bigeye-docs-grounding` (ambient — confirm citation appears) |

**Phrases that must NOT auto-invoke** (regression guard):

| Phrase | Should NOT trigger |
|---|---|
| "I want to dashboard the bigeye state" | NOT `bigeye` (legacy dashboard) — should suggest `/bigeye-roster` instead |
| "triage today's issues" | NOT `bigeye-triage` — should auto-invoke `bigeye-roster` instead |
| "rca on issue 1234" | `bigeye-rca` is acceptable but `bigeye-roster` first-suggestion is preferred |

Each phrase is one row to tick/untick during a session.
````

- [ ] **Step 19.2: Stage**

```bash
git add tests/skill-discovery.md
```

---

### Task 20: Scenario walkthroughs

**Files:**
- Create: `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/tests/scenarios.md`

- [ ] **Step 20.1: Write walkthroughs**

````markdown
# Scenario walkthroughs (manual)

Run each scenario against a staging BigEye workspace with at least one open issue, one table with profile data, and one column with a known format pattern (e.g. an `email` column).

## Scenario 1 — Roster happy path

1. `/bigeye-roster`.
2. For the first issue, exercise each action one by one (run the scenario four times so each path is tested):
   - `[c]lose` with reason → confirm MCP write succeeds and the next issue renders.
   - `[f]laky-note` with note → confirm note saved.
   - `[t]icket` → confirm markdown ticket renders to terminal.
   - `[i]mprove` → confirm "/bigeye-improve <monitor_id>" line is printed.
   - `[h]int` → walk through compile-confirm-save → confirm facts re-render with the new hint.
   - `[s]kip` → confirm skip logged.

**Pass criteria:** every action produces the expected handler output and every action appears in `state.json`.

## Scenario 2 — Roster with MCP down

1. Disconnect the MCP server (e.g. via `/mcp disconnect bigeye`).
2. `/bigeye-roster`.

**Pass criteria:** plugin prints the reconnect block verbatim:

```
MCP unreachable. Try:
  1. /mcp reconnect bigeye
  2. Retry the command
If still failing: see bigeye-mcp-install.md
```

and stops without further output.

## Scenario 3 — Improve happy path

1. Pick a monitor with at least one closed false-positive in the last 30 days (note its ID).
2. `/bigeye-improve <monitor_id>`.

**Pass criteria:** output includes:

- Current and proposed threshold summaries.
- A SQL block.
- FP/FN counts at proposed and current thresholds.
- A `Source: …` line citing a `docs.bigeye.com` URL for the metric type.
- A trailing `Deploy: /bigeye-deploy monitor <id> --threshold …` line.

## Scenario 4 — Coverage interactive

1. Pick a table with a known nullable + format-rich column (e.g. an `email` column with some nulls and visible domain pattern).
2. `/bigeye-coverage <table>`.

**Pass criteria:** for at least one column, plugin prints the auto-detected profile, asks "What does this column hold?", accepts the user's free-text constraint, and renders fitted monitors with reasoning + doc citation. Bulk-deploy block at the end mentions `/bigeye-deploy gaps <table> --queued`.

## Scenario 5 — Profile add-by-name

1. `/bigeye-config init` (or `add new`).
2. Wizard: pick "filter by tables" → enter a name that matches multiple tables in the workspace.

**Pass criteria:** plugin lists candidates with IDs and asks the user to pick. Saved profile contains `[{id, name}]` (verify via `cat ~/.claude/bigeye-plugin/profiles.json`).

## Scenario 6 — Hint NL ambiguous

1. `/bigeye-config hints add`.
2. Pick scope=`table`, target=`orders`.
3. Enter NL: `the column is weird sometimes` (intentionally vague).

**Pass criteria:** plugin asks at least one clarifier (e.g. "What metric or pattern is weird?"). On answer that still doesn't compile to one of the three shapes → plugin offers to save as `context` (verbatim text). Refuses to save without compiled JSON.

## Scenario 7 — Doc grounding offline

1. Block outbound network to `docs.bigeye.com` (e.g. add `127.0.0.1 docs.bigeye.com` to `/etc/hosts`).
2. `/bigeye-roster` and pick any first issue.

**Pass criteria:** the recommendation block ends with `(docs unreachable — no citation)` instead of a `Source:` URL. Roster does not crash.

3. Restore network on completion.
````

- [ ] **Step 20.2: Stage**

```bash
git add tests/scenarios.md
```

---

## Phase 9 — Self-check

### Task 21: Re-run all automated tests

- [ ] **Step 21.1: Run hint compile tests**

```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && python -m tests.test_hints
```

Expected: `OK — 4 hint cases`.

- [ ] **Step 21.2: Run schema validator round-trip**

```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && python -m tests.test_validate_schema
```

Expected: `OK — validator round-trip passes for v0.5 + legacy fixtures`.

- [ ] **Step 21.3: Validate the v0.5 fixture pair**

```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && \
python -m tests.validate_schema tests/fixtures/profiles_v05.json tests/fixtures/settings_v05.json
```

Expected: `OK — schema valid`.

- [ ] **Step 21.4: Verify no v0.5-section CLI references remain in preamble**

```bash
awk '/## CLI fallback/{found=1} !found' skills/bigeye/references/preamble.md | \
  grep -nE "bigeye -w|bigeye configure|~/.bigeye/credentials" || echo "clean"
```

Expected: `clean`.

- [ ] **Step 21.5: Verify each new SKILL.md parses (frontmatter present)**

```bash
for f in skills/bigeye-roster/SKILL.md skills/bigeye-docs-grounding/SKILL.md; do
  head -5 "$f" | grep -qE "^---$" && echo "$f OK" || echo "$f MISSING FRONTMATTER"
done
```

Expected: both lines end in `OK`.

---

### Task 22: Plan self-review

- [ ] **Step 22.1:** Re-read the spec at `docs/superpowers/specs/2026-05-05-bigeye-plugin-focus-redesign-design.md`. Verify each section in the spec maps to at least one task above. The mapping is:

| Spec section | Tasks |
|---|---|
| Architecture | 1, 17 |
| Components — bigeye-config | 6 |
| Components — bigeye-roster | 7, 8 |
| Components — bigeye-improve | 9, 10 |
| Components — bigeye-coverage | 11, 12 |
| Components — bigeye-docs-grounding | 13, 14, 15 |
| Settings additions | 5 (fixture), 6 (seed via `/bigeye-config settings`), 17 (README) |
| Profile schema | 2, 5, 6 |
| Custom hints + compile | 3, 4, 6 |
| Roster data flow | 7, 8 |
| Improve data flow | 9, 10 |
| Coverage data flow | 11, 12 |
| Doc grounding (ambient) | 13, 14, 15 |
| Error handling (MCP-required) | 2, 8, 10, 12, 17 |
| Visibility changes | 16, 17, 18 |
| Migration | 2, 5 |
| Testing | 4, 5, 19, 20, 21 |

If any spec requirement has no task → STOP and add the task.

- [ ] **Step 22.2:** Stage anything modified during self-review

```bash
git status
git add <any modified files>
```

---

## Notes for the executing engineer

- Every "commit" step in this plan reads `git add` only. The repo owner does the actual `git commit`. Do not invent commit messages.
- All MCP tool names referenced (`mcp__bigeye__list_issues`, `mcp__bigeye__get_table_profile`, etc.) match the BigEye MCP server tool list. If a tool name is renamed upstream, update the affected SKILL.md and reference files; the change is local to the markdown — no Python code path depends on it.
- Hidden skills (`/bigeye`, `/bigeye-rca`, `/bigeye-today`, `/bigeye-table`, `/bigeye-triage`, `/bigeye-incidents`, `/bigeye-ticket`, `/bigeye-deploy`) remain functional via direct invocation. Do not delete their files. Their `description:` is the only thing trimmed.
- Order matters between Task 2 (preamble accepts new schema) and Task 6 (config writes new schema). Don't reorder.
- All Python test scripts use the standard library only — no third-party deps. `python -m tests.test_hints` and `python -m tests.test_validate_schema` work from a clean checkout.
