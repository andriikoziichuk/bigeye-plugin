---
name: bigeye-roster
description: Use when the user wants to walk today's BigEye issues — daily routine that gathers facts per issue, presents a recommendation, and lets the user pick the action. Advisory only; the user decides every action.
user-invocable: true
---

# BigEye Daily Roster Routine

What it does: iterates open issues in the active profile's scope. Per issue: gathers facts, derives a recommendation, prints a short rendering, asks the user to pick an action. Advisory — never auto-closes anything.

Follow `skills/bigeye/references/preamble.md` Steps 1–7 first. Hard-fail per Step 7.E when MCP is unreachable. Facts/recommendation/action handlers live in `skills/bigeye/references/roster.md`. Output shape lives in `skills/bigeye/references/output.md`.

## Arguments

| Invocation | Behavior |
|---|---|
| (empty) | Walk active profile's open issues |
| `--include-actioned` | Include issues actioned in the last 24h (otherwise skipped) |
| `--limit <N>` | Stop after N issues |
| `--batch <N>` | Override `settings.roster.batch_size` |
| `--profile <name>` | Use named profile for this run |

Global flags from `output.md` apply.

## Procedure

1. Follow `preamble.md` Steps 1–7. Hard-fail per Step 7.E when MCP is off — print the reconnect block and stop.
2. Build the issue list:
   - `mcp__bigeye__list_issues` with profile-derived parameter map (workspace_id, data_source_ids, table_ids, schema_names, dimension_ids from `monitored_rules`).
   - Filter to `status in {NEW, ACKNOWLEDGED}`.
   - Apply resumability filter from `roster.md` unless `--include-actioned`.
   - Order by `(severity desc, opened_at asc)`.
3. Loop in batches of `settings.roster.batch_size` (overridden by `--batch`):
   - For each issue, gather facts per `roster.md` §"Fact gathering". Gather in parallel where MCP supports it.
   - Derive recommendation per `roster.md` §"Recommendation derivation".
   - Render per `roster.md` §"Render template". Cite a docs URL for the dimension involved (delegate to `bigeye-docs-grounding`).
   - Wait for user action input. Run the matching handler from `roster.md` §"Action handlers".
4. After each batch, print the batch summary line and ask `Continue? (y/n)`.
5. End-of-pass summary:
   ```
   Roster complete — {N} issues reviewed.
     close: {x}    flaky-note: {y}    ticket: {z}
     improve suggested: {q}    hint added: {h}    skip: {s}
   ```
6. Footer:
   ```
   Next: /bigeye-roster --include-actioned     (re-walk including recently-actioned)
   More: /bigeye-improve <monitor_id>  ·  /bigeye-coverage <table>  ·  /bigeye-config hints list
   ```

## State persistence

Per action: append `{skill:"bigeye-roster", action:"<key>", at:<iso8601>, reason:<optional>}` to `state.json.issues[<id>].actions`. Update `state.last_workflow = "bigeye-roster"`. Run pruning per preamble Step 8.C.

## Errors

- MCP unreachable at start → reconnect block (preamble 7.E) and stop.
- MCP fails mid-loop on a single fact → mark `(unavailable)`; continue.
- MCP fails mid-loop on an action write → Error/Fix/Why block; ask retry/skip/stop.
- User answers an unknown key in the action prompt → repeat the menu once; on second unknown → skip.
