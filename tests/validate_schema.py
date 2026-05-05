"""Schema validators for BigEye plugin config files.

Run as: python3 -m tests.validate_schema <profiles.json> <settings.json>
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
        print("usage: python3 -m tests.validate_schema <profiles.json> <settings.json>")
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
