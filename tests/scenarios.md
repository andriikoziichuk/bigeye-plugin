# Scenario walkthroughs (manual)

Run each scenario against a staging BigEye workspace with at least one open issue, one table with profile data, and one column with a known format pattern (e.g. an `email` column).

## Scenario 1 — Roster happy path

1. `/bigeye-roster`.
2. For the first issue, exercise each action one by one (run the scenario four times so each path is tested):
   - `[c]lose` with reason → confirm MCP write succeeds and the next issue renders.
   - `[f]laky-note` with note → confirm note saved.
   - `[t]icket` → confirm markdown ticket renders to terminal.
   - `[i]mprove` → confirm "/bigeye-improve <monitor_id>" line is printed.
   - `[h]int` → walk through compile-confirm-save → confirm facts re-render with the new hint.
   - `[s]kip` → confirm skip logged.

**Pass criteria:** every action produces the expected handler output and every action appears in `state.json`.

## Scenario 2 — Roster with MCP down

1. Disconnect the MCP server (e.g. via `/mcp disconnect bigeye`).
2. `/bigeye-roster`.

**Pass criteria:** plugin prints the reconnect block verbatim:

```
MCP unreachable. Try:
  1. /mcp reconnect bigeye
  2. Retry the command
If still failing: see bigeye-mcp-install.md
```

and stops without further output.

## Scenario 3 — Improve happy path

1. Pick a monitor with at least one closed false-positive in the last 30 days (note its ID).
2. `/bigeye-improve <monitor_id>`.

**Pass criteria:** output includes:

- Current and proposed threshold summaries.
- A SQL block.
- FP/FN counts at proposed and current thresholds.
- A `Source: …` line citing a `docs.bigeye.com` URL for the metric type.
- A trailing `Deploy: /bigeye-deploy monitor <id> --threshold …` line.

## Scenario 4 — Coverage interactive

1. Pick a table with a known nullable + format-rich column (e.g. an `email` column with some nulls and visible domain pattern).
2. `/bigeye-coverage <table>`.

**Pass criteria:** for at least one column, plugin prints the auto-detected profile, asks "What does this column hold?", accepts the user's free-text constraint, and renders fitted monitors with reasoning + doc citation. Bulk-deploy block at the end mentions `/bigeye-deploy gaps <table> --queued`.

## Scenario 5 — Profile add-by-name

1. `/bigeye-config init` (or `add new`).
2. Wizard: pick "filter by tables" → enter a name that matches multiple tables in the workspace.

**Pass criteria:** plugin lists candidates with IDs and asks the user to pick. Saved profile contains `[{id, name}]` (verify via `cat ~/.claude/bigeye-plugin/profiles.json`).

## Scenario 6 — Hint NL ambiguous

1. `/bigeye-config hints add`.
2. Pick scope=`table`, target=`orders`.
3. Enter NL: `the column is weird sometimes` (intentionally vague).

**Pass criteria:** plugin asks at least one clarifier (e.g. "What metric or pattern is weird?"). On answer that still doesn't compile to one of the three shapes → plugin offers to save as `context` (verbatim text). Refuses to save without compiled JSON.

## Scenario 7 — Doc grounding offline

1. Block outbound network to `docs.bigeye.com` (e.g. add `127.0.0.1 docs.bigeye.com` to `/etc/hosts`).
2. `/bigeye-roster` and pick any first issue.

**Pass criteria:** the recommendation block ends with `(docs unreachable — no citation)` instead of a `Source:` URL. Roster does not crash.

3. Restore network on completion.
