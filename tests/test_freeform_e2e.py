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

    out = template
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
    for m in re.finditer(r"\{\{\^([\w.]+)\}\}(.*?)\{\{/\1\}\}", template, re.DOTALL):
        path, inner = m.group(1), m.group(2)
        val = lookup(view, path)
        replacement = render(inner, view) if not val else ""
        out = out.replace(m.group(0), replacement)
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

    if "Investigation — D-7a3f" not in rendered:
        failures.append("e2e: rendered memo missing freeform header (Investigation — D-7a3f)")
    if "_user-provided query_" not in rendered:
        failures.append("e2e: rendered trace table missing _user-provided query_ label for seed row")
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
