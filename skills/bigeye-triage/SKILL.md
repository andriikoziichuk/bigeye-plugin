---
name: bigeye-triage
description: Use when the user wants to see active BigEye issues, asks what's broken or on fire, or needs a prioritized view of data quality problems
user-invocable: true
---

# BigEye Triage

What it does: fetches all active issues, applies the active scope, and renders a prioritized table of New / Ack'd / Monitoring issues. Atomic — no menus. Building block called by `/bigeye-today`.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`.

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| (no arg) | All open issues (NEW + ACKNOWLEDGED + MONITORING) | `/bigeye-triage` |
| `new` | Only NEW status issues | `/bigeye-triage new` |
| `24h` | Issues opened in the last 24 hours | `/bigeye-triage 24h` |
| `<integer>` | Override `triage.max_issues` | `/bigeye-triage 100` |

Global flags (`--profile`, `--no-scope`, `--workspace`, `--full`, `--limit`, `--verbose`) — see `output.md`.

## Procedure

1. Follow `preamble.md` Steps 1–7. Read `settings.json.triage.max_issues` and `triage.default_brief_rows`.

2. Fetch open issues via CLI:
   ```bash
   TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
   trap 'rm -rf "$TMPDIR"' EXIT
   bigeye -w <profile> issues get-issues \
     {-wid <id> per data_source_id} \
     {-sn <name> per schema_name} \
     -op "$TMPDIR"
   ```
   Parse every JSON file in `$TMPDIR`. Filter:
   - Status in `{NEW, ACKNOWLEDGED, MONITORING}`. With `new` arg → `NEW` only. With `24h` arg → `openedAt` within 24 hours.
   - Table filter: build `effective_table_ids = union(profile.table_ids, resolved(profile.table_names))`. If non-empty, keep only issues whose `metricMetadata.datasetId` is in that set. (CLI has no table flag — this filter is post-fetch.)
   - Cap at `max_issues` (default 50, or the integer argument if given).

   If the filtered list is empty, print the empty-result line per `output.md` and stop after the footer.

   When MCP is unavailable and `table_names` couldn't resolve to IDs, print one warning line listing unresolved names; fall back to `effective_table_ids = profile.table_ids` alone.

3. Cluster detection:
   - `MCP_AVAILABLE=true`: for each open issue, call `mcp__bigeye__list_related_issues` with `starting_issue_id`. Count related issues per issue. Flag any with 2+ related as a cluster.
   - `MCP_AVAILABLE=false`: emit the MCP-absent warning per `preamble.md` Step 7.B with `feature_name=cluster detection`. Set `cluster_count=null`.

4. Render output. Group by `currentStatus` — one section per bucket (New / Ack'd / Monitoring). Sort rows within each bucket by `priorityScore` desc.

   Brief default: top `default_brief_rows` (10) per bucket. `--full` shows all. `--limit N` overrides count.

   ```
   {scope pill}
   ## BigEye Triage — {today's date}

   ### New ({count})
    # | Issue | Score | Dim | Table | Column | Since | History
    1 | 10921 |  87   | Freshness | orders | — | 2h | rca (4d)
    ...
   (<N more> — add --full to see all)

   ### Ack'd ({count})
    # | Issue | Score | Dim | Table | Column | Since | History
    ...

   ### Monitoring ({count})
    # | Issue | Score | Dim | Table | Column | Since | History
    ...

   Summary: {new_count} new · {ackd_count} ack'd · {monitoring_count} monitoring · {cluster_count} clusters
   ```

   `History` is sourced from `state.json.issues[<display_name>].actions` — last 2 distinct skill names + age (`rca (4d)`). Empty → `—`.

   If `cluster_count == null`, render `cluster detection: unavailable` instead.

   Status order is always New → Ack'd → Monitoring. Empty sections are omitted.

5. Footer:
   ```
   Next: /bigeye-rca {top-scored display_name}     (top-scored, not yet investigated)
   More: /bigeye-today  ·  /bigeye-incidents auto  ·  /bigeye  (dashboard)
   ```
   If clusters exist: replace the `Next:` value with `Next: /bigeye-incidents auto     ({cluster_count} clusters detected)`.

## State persistence

On successful render, follow `preamble.md` Step 8.B for the `bigeye-triage` row: update `state.json.issues[<display_name>].last_seen` and `status_when_last_seen` for every listed issue. Do **not** append to `actions[]`. Do not change `last_issue` or `last_table`.

Then run pruning per Step 8.C.

## Errors

CLI / scope / parse errors: per `preamble.md` Step 7.D. No skill-specific error paths.
