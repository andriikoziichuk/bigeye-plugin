"""Unit tests for tools.freeform_intake."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "freeform_intake_cases.json"

sys.path.insert(0, str(REPO))
from tools import freeform_intake  # noqa: E402


def check_table_extraction(cases: list) -> list[str]:
    failures: list[str] = []
    for c in cases:
        got = freeform_intake.extract_table(c["input"])
        if got != c["expect_table"]:
            failures.append(f"table_extraction: {c['input']!r}: want {c['expect_table']!r}, got {got!r}")
    return failures


def check_sql_extraction(cases: list) -> list[str]:
    failures: list[str] = []
    for c in cases:
        got = freeform_intake.extract_sql(c["input"])
        want = c["expect_sql"]
        if want is None:
            if got is not None:
                failures.append(f"sql_extraction: {c['input']!r}: want None, got {got!r}")
        else:
            if (got or "").strip() != want.strip():
                failures.append(f"sql_extraction: {c['input']!r}: want {want!r}, got {got!r}")
    return failures


def check_time_hint(cases: list) -> list[str]:
    failures: list[str] = []
    for c in cases:
        got = freeform_intake.extract_time_hint(c["input"])
        if got != c["expect"]:
            failures.append(f"time_hint: {c['input']!r}: want {c['expect']!r}, got {got!r}")
    return failures


def check_issue_type(cases: list) -> list[str]:
    failures: list[str] = []
    for c in cases:
        got = freeform_intake.infer_issue_type(c["input"])
        if got != c["expect"]:
            failures.append(f"issue_type: {c['input']!r}: want {c['expect']!r}, got {got!r}")
    return failures


def check_parse(cases: list) -> list[str]:
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


def main() -> int:
    cases = json.loads(FIXTURE.read_text())
    failures: list[str] = []
    failures += check_table_extraction(cases["table_extraction"])
    failures += check_sql_extraction(cases["sql_extraction"])
    failures += check_time_hint(cases["time_hint"])
    failures += check_issue_type(cases["issue_type"])
    failures += check_parse(cases["parse"])
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("OK — freeform_intake checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
