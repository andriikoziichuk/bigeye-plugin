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
