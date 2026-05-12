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
