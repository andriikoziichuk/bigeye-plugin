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
