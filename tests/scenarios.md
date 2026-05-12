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

## Scenario 8 — Investigator happy path

### Setup

1. Ensure at least one open BigEye issue exists for a Snowflake table that has recent query history in `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY` (or `INFORMATION_SCHEMA.ACCESS_HISTORY`).
2. Confirm the MCP server is reachable (`/mcp status bigeye` shows connected).
3. Confirm `state.json` exists (or will be created) at `~/.claude/bigeye-plugin/state.json`.

### Run

1. `/bigeye-investigate <issue_id>` where `<issue_id>` is the ID of the open issue identified in Setup.

### Pass criteria

- Skill prints a structured investigation report that includes:
  - Issue summary (ID, metric type, table, column, breach value).
  - Access history query result citing `INFORMATION_SCHEMA.ACCESS_HISTORY` (user list or "no recent writers found").
  - Upstream lineage section (from `get_upstream_root_causes` or `get_lineage_graph`).
  - A ranked root-cause hypothesis list.
  - A recommended next action (one of: close, ticket, improve, escalate).
- `state.json.last_investigation` is updated with the issue ID and ISO timestamp.
- No uncaught exceptions; skill exits cleanly.

### Negative

- Re-run immediately for the same issue ID.
- **Pass:** skill detects `state.json.last_investigation` matches, prints a "already investigated recently" notice, and prompts before re-running (or skips with a notice).

## Scenario 9 — Investigator with subagent timeout (synthetic)

### Setup

1. Identify an issue ID that exists in BigEye but whose table has **no** rows in `INFORMATION_SCHEMA.ACCESS_HISTORY` for the last 7 days (or simulate by picking a table name that will return an empty result set).
2. Set an env var `BIGEYE_INVESTIGATE_TIMEOUT_MS=500` (or equivalent config) so the access-history subagent times out quickly; if the skill does not support this env var, simply note the expected behavior and verify manually with a table known to be slow.

### Run

1. `/bigeye-investigate <issue_id>` using the issue from Setup.

### Pass criteria

- Skill does **not** crash or hang indefinitely.
- Output contains a clearly marked `[access-history: timeout or no data]` notice (or equivalent) in place of the access-history section.
- Upstream lineage and hypothesis sections still render (degraded-graceful mode).
- `state.json.last_investigation` is still written with the issue ID and timestamp even when the subagent timed out.
- Overall wall-clock time does not exceed 60 seconds for the complete run.

## Scenario: Freeform debug — pasted prose + SQL (live)

Setup: a Snowflake profile that connects, any in-scope table you can read.

Run:

```
/bigeye-investigate "rows missing from <SCHEMA.TABLE> in the last 7 days. ran this:
```sql
SELECT COUNT(*) FROM <SCHEMA.TABLE> WHERE loaded_at >= DATEADD(day, -7, CURRENT_DATE)
```
"
```

Expected:
1. Intake confirmation block shows:
   - Table: `<SCHEMA.TABLE>`
   - Filter: `loaded_at >= DATEADD(day, -7, CURRENT_DATE)`
   - Issue type: `volume`
   - Pack: `_default` (or matched pack if the table has tags)
   - Budget: `10`
   - Seed query: `yes (will run as query #0)`
2. After `y`, streaming shows `[query 1/10] seed :: ...` followed by pack hypothesis queries.
3. Memo header reads `Investigation — D-<4-hex>`.
4. Trace table row 1 shows `_user-provided query_` in the second column.
5. State file `~/.claude/bigeye-plugin/state.json` now has `last_freeform_investigation` set; `last_issue` is unchanged.
6. Trace file `~/.claude/bigeye-plugin/investigations/D-<short>-<iso>.json` exists.

## Scenario: Freeform debug — guard rejects pasted SQL

Run:

```
/bigeye-investigate "fixing PROD.ORDERS: \n```sql\nDELETE FROM PROD.ORDERS\n```"
```

Expected:
```
Error: pasted SQL rejected by read-only guard: forbidden keyword 'delete'.
Fix:   remove the write statement and re-run.
```
State file is untouched.

## Scenario: Freeform debug — required-fields exhaustion

Run:

```
/bigeye-investigate "something is broken"
```

Expected: three clarifying-question rounds. If you answer all of them blank, after round 3:

```
Error: not enough info to investigate.
Fix:   /bigeye-investigate "<your description>" --table SCHEMA.TABLE --since 7d --type volume
Why:   need table, time scope, and issue type to run hypotheses.
```

