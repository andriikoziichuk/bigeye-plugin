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
    ("good_minimal",               0, []),
    ("bad_missing_tags",           1, ["tags"]),
    ("bad_unique_id",              1, ["unique", "same-id"]),
    ("bad_filter_mirroring",       1, ["filter mirroring", "no-filter-no-widening"]),
    ("bad_empty_tags_user_pack",   1, ["tags"]),
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
