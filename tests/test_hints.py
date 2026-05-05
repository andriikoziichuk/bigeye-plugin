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
