"""Pack template render CLI.

Usage:
  python -m tools.pack_render --template "<tmpl>" --vars '<json>'

Substitutes {{name}} placeholders with corresponding JSON values. Missing
variables render as empty string. Prints result to stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys


PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def render(template: str, variables: dict) -> str:
    def repl(m: re.Match) -> str:
        return str(variables.get(m.group(1), ""))
    return PLACEHOLDER.sub(repl, template)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--template", required=True)
    p.add_argument("--vars", required=True)
    args = p.parse_args(argv[1:])
    try:
        variables = json.loads(args.vars)
    except json.JSONDecodeError as e:
        print(f"error: invalid --vars JSON: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(render(args.template, variables))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
