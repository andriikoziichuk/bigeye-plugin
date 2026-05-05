---
name: bigeye-coverage
description: Use when the user wants to find monitoring gaps, check which columns or dimensions lack monitors, or assess overall monitoring coverage on their table
user-invocable: true
---

# BigEye Coverage Analysis

What it does: scores dimension coverage on a table (or the in-scope tables), prioritizes gaps using past issue history, and surfaces cheap weak-monitor findings inline.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`.

## Arguments

| Invocation | Purpose |
|---|---|
| `<table>` | Run interactive coverage on the named table |
| (no arg) | Resume `state.json.last_table` if set, else ask which table |
| `--profile <name>` | Run with a non-active profile |

Global flags — see `output.md`.

## Procedure

1. Hard-fail per preamble Step 7.E if MCP is off.
2. Follow preamble Steps 1–7.
3. Resolve target table → `table_id`. Argument given → use it (ambiguity → user picks). No argument: use `state.json.last_table` if set, else ask.
4. Run the procedure in `skills/bigeye/references/coverage-interactive.md`.
5. Footer:
   ```
   Next: /bigeye-deploy gaps {table} --queued     ({queued_count} queued monitors)
   More: /bigeye-improve <monitor_id>  ·  /bigeye-roster
   ```

## State persistence

On successful render, follow `preamble.md` Step 8.B for the `bigeye-coverage` row:
- Set `state.json.last_table = "<schema.table>"` (or the fully-qualified target).
- Append `{ skill: "bigeye-coverage", at: <iso8601> }` to `state.json.tables[<fq>].actions`.
- Update `first_seen` (if absent) and `last_seen`.

Then run pruning per Step 8.C.

## Errors

- MCP unreachable → preamble 7.E reconnect block. Stop.
- Table not found → `Table {name} not found in workspace. Fix: /bigeye-config show to confirm scope.`
- Per-column profile fetch fails → annotate `(profile unavailable for {column})` and continue.
