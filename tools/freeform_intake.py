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


_KEYWORDS = {
    "freshness": [r"\bstale\b", r"\bnot updated\b", r"\bsince\b.*\b(ago|days?|hours?|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"],
    "volume": [r"\bmissing rows\b", r"\brows missing\b", r"\bempty\b", r"\brow count\b", r"\bfewer rows\b"],
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
