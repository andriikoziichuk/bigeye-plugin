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


def _collapse_commented_semicolons(s: str) -> str:
    """Replace '; -- comment\n' with '\n' so trailing-comment semicolons
    are not counted as statement separators during multi-statement detection."""
    return re.sub(r";\s*--[^\n]*\n", "\n", s)


def _strip_line_comments(s: str) -> str:
    return re.sub(r"--[^\n]*", " ", s)


def assert_readonly(sql: str) -> None:
    if sql is None:
        raise GuardError("null sql")
    s = sql
    s = _strip_block_comments(s)
    s = _collapse_commented_semicolons(s)
    s = _strip_line_comments(s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    if not s:
        raise GuardError("empty query")
    first = s.split(" ", 1)[0]
    if first not in {"select", "with"}:
        raise GuardError(f"first token {first!r}; expected select|with")
    stmts = [x for x in s.rstrip(";").split(";") if x.strip()]
    if len(stmts) > 1:
        raise GuardError(f"{len(stmts)} statements found; only one SELECT allowed")
    for kw in DENY:
        if re.search(rf"\b{kw}\b", s):
            raise GuardError(f"forbidden keyword {kw!r}")
    if re.search(r"\binto\b", s):
        raise GuardError("'into' clause not allowed")


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
