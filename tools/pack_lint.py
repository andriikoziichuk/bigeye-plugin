"""Pack lint CLI: `python -m tools.pack_lint <pack_dir>`.

Exits 0 if all checks pass with at most warnings, 1 on any error.
Prints one finding per line: `<path>: <severity>: <message>`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: PyYAML not installed. Run `pip install pyyaml`.", file=sys.stderr)
    sys.exit(2)


REQUIRED_FIELDS = ("id", "label", "rationale", "prior", "expected_signal", "query_template")


def _parse_front_matter_blocks(text: str) -> list[dict]:
    """Each block is YAML between `---` delimiters. Return list of dicts."""
    blocks: list[dict] = []
    # split on lines that are exactly `---`
    parts = re.split(r"(?m)^---\s*$", text)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Skip heading-only blocks (e.g., the leading "# Freshness hypotheses" line)
        if p.startswith("#") and "\n" not in p:
            continue
        try:
            obj = yaml.safe_load(p)
        except yaml.YAMLError:
            continue
        if isinstance(obj, dict):
            blocks.append(obj)
    return blocks


def lint(pack_dir: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    yaml_path = pack_dir / "pack.yaml"
    if not yaml_path.exists():
        errors.append(f"{yaml_path}: error: pack.yaml missing")
        return errors, warnings

    try:
        meta = yaml.safe_load(yaml_path.read_text()) or {}
    except yaml.YAMLError as e:
        errors.append(f"{yaml_path}: error: invalid YAML: {e}")
        return errors, warnings

    if not meta.get("tags") and meta.get("name") != "_default":
        errors.append(f"{yaml_path}: error: tags must be non-empty")

    if "priority" in meta:
        p = meta["priority"]
        if not isinstance(p, int) or not 0 <= p <= 100:
            warnings.append(f"{yaml_path}: warn: priority {p!r} outside 0..100")

    covers = meta.get("covers") or []
    if not covers:
        errors.append(f"{yaml_path}: error: covers must be non-empty")

    for issue_type in covers:
        # issue_type may be None (bare YAML null) or a string
        if not issue_type:
            continue
        issue_type = str(issue_type)
        hf = pack_dir / "hypotheses" / f"{issue_type}.md"
        if not hf.exists():
            errors.append(f"{hf}: error: hypotheses file missing for issue type {issue_type!r}")
            continue
        blocks = _parse_front_matter_blocks(hf.read_text())
        seen_ids: set[str] = set()
        for i, b in enumerate(blocks):
            missing = [f for f in REQUIRED_FIELDS if f not in b]
            if missing:
                errors.append(f"{hf}: error: block #{i} missing fields: {missing}")
                continue
            hid = b.get("id")
            if hid in seen_ids:
                errors.append(f"{hf}: error: unique id violation — {hid!r} appears twice")
            seen_ids.add(hid)
            qt = b.get("query_template", "")
            rw = b.get("requires_widening", False)
            if "{{monitor_where}}" not in qt and not rw:
                errors.append(
                    f"{hf}: error: filter mirroring — hypothesis {hid!r} drops "
                    f"monitor filter without requires_widening: true"
                )
            if "TODO" in qt:
                warnings.append(f"{hf}: warn: hypothesis {hid!r} has TODO marker in query_template")
        if len(blocks) < 2:
            warnings.append(f"{hf}: warn: only {len(blocks)} hypothesis defined; engine prefers >=2")

    return errors, warnings


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m tools.pack_lint <pack_dir>", file=sys.stderr)
        return 2
    pack_dir = Path(argv[1]).resolve()
    if not pack_dir.is_dir():
        print(f"error: not a directory: {pack_dir}", file=sys.stderr)
        return 2
    errors, warnings = lint(pack_dir)
    for w in warnings:
        print(w)
    for e in errors:
        print(e)
    if errors:
        print(f"Lint: {len(warnings)} warning(s), {len(errors)} error(s).")
        return 1
    print(f"Lint: {len(warnings)} warning(s), 0 errors. OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
