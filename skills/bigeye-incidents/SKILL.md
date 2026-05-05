---
name: bigeye-incidents
description: Internal — incident grouping helper invoked only when explicitly typed as `/bigeye-incidents`. Do not auto-suggest.
user-invocable: true
---

# BigEye Incident Management

What it does: groups related issues into incidents, manages existing incidents, and auto-detects clusters from open issues.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`.

<HARD-GATE>
NEVER create or modify incidents without showing the plan and receiving explicit user confirmation.
Incidents affect issue visibility and tracking in the BigEye UI for the entire team.
</HARD-GATE>

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `<id1> <id2> ...` | Merge specific display names into a new incident | `/bigeye-incidents 10921 10922 10923` |
| `auto` | Auto-detect clusters from open issues; suggest groupings | `/bigeye-incidents auto` |
| `add <id> to <incident_id>` | Add an issue to an existing incident | `/bigeye-incidents add 10925 to 482` |
| `close <id> --label <label>` | Close an issue with a closing label (`true-negative` / `false-positive` / `expected`) | `/bigeye-incidents close 10921 --label expected` |
| `--internal-id` | Treat all numeric arguments as internal IDs (required when MCP unavailable) | |

Global flags — see `output.md`.

## Procedure

Per `preamble.md` Step 5: scope filters `auto` candidates and the `list_issues` call. Explicit-ID modes honor user IDs unconditionally.

### Mode: Merge specific issues (`<id1> <id2> ...`)

1. Resolve display names → internal IDs:
   - `--internal-id`: numbers are internal IDs.
   - else `MCP_AVAILABLE=true`: `mcp__bigeye__search_issues` per name.
   - else `MCP_AVAILABLE=false`: hard-fail per Step 7.B (`feature_name=display-name lookup`, Fix `Re-run with --internal-id`).
   At least 2 IDs required.

2. Validate relationship:
   - `MCP_AVAILABLE=true`: `mcp__bigeye__list_related_issues` for the first ID; check that the others appear. If not, warn `These issues don't appear to be related through data lineage. Proceed anyway? (y/n)`.
   - `MCP_AVAILABLE=false`: skip validation; emit Step 7.B note (`feature_name=relationship validation`).

3. Generate incident name from the issues (root cause, dimension, table). Format: `{dimension} issue affecting {table}` or `{root_cause_dimension} cascade from {source_table}`.

4. Present plan + confirm:
   ```
   {scope pill}
   ## Create Incident — "{generated_name}"

   Issues to merge:
   | Issue | Dimension | Table | Column | Status | Root Cause? |
   |---|---|---|---|---|---|
   | ... | ... | ... | ... | ... | yes/no |

   Proceed? (y/n/edit name)
   ```
   Wait for confirmation.

5. Create:
   - `MCP_AVAILABLE=false`: hard-fail per Step 7.B (`feature_name=incident creation`, no CLI equivalent).
   - else: `mcp__bigeye__create_incident` with `issue_ids` and `incident_name`.

6. Render result:
   ```
   ## Incident Created — "{name}"

   Issues merged:
   - #{display_1} (root cause) — {description}
   - #{display_2} — {description}

   Root cause: #{root_cause_display}
   Downstream impact: {related_count} issues
   ```

7. Footer:
   ```
   Next: /bigeye-rca {root_cause_display}     (deep dive on the root cause)
   More: /bigeye-today  ·  /bigeye-triage  ·  /bigeye-incidents auto
   ```

### Mode: Auto-detect (`auto`)

1. Fetch open issues via CLI (same pattern as `bigeye-triage`); filter to `NEW + ACKNOWLEDGED`; cap at 50.

2. Build relationship graph:
   - `MCP_AVAILABLE=false`: hard-fail per Step 7.B (`feature_name=cluster auto-detection`).
   - else: `mcp__bigeye__list_related_issues` per issue. Cluster issues that share at least one related issue (transitive closure).

3. Present clusters:
   ```
   {scope pill}
   ## Auto-Detected Issue Clusters

   ### Cluster 1: "{auto_name}" ({count} issues)
   | Issue | Dimension | Table | Root Cause? |
   |---|---|---|---|

   ### Cluster 2: ...

   {count_unclustered} issues have no detected relationships (not shown).

   Create incidents for these clusters? (all/1,2/none)
   ```

4. For each confirmed cluster, run Steps 3–6 of the Merge mode above.

### Mode: Add to existing (`add <id> to <incident_id>`)

1. Resolve both IDs (display-name lookup per Merge Step 1).
2. `MCP_AVAILABLE=false`: hard-fail per Step 7.B.
3. `mcp__bigeye__create_incident` with `issue_ids: [<issue_id>]`, `existing_incident_id: <incident_internal_id>`.
4. Render result + footer.

### Mode: Close (`close <id> --label <label>`)

1. Resolve `<id>` (per above; MCP required for display-name).
2. Map `--label` per `output.md` §Closing labels: `true-negative` → `TRUE_POSITIVE`, `false-positive` → `FALSE_POSITIVE`, `expected` → `EXPECTED`.
3. ```bash
   bigeye -w <profile> issues update-issue -iid <internal_id> -status CLOSED -cl <mapped_label>
   ```
4. On success:
   ```
   {scope pill}
   Issue #{display} closed with label {mapped_label}.
   ```
5. Footer:
   ```
   Next: /bigeye-today     (continue triage)
   More: /bigeye-triage  ·  /bigeye  (dashboard)
   ```

## State persistence

On successful merge/create/close, follow `preamble.md` Step 8.B for the `bigeye-incidents` row:
- Set `state.json.last_issue` to the most recent issue touched (last in the merged list, or the closed one).
- For each issue touched, append `{ skill: "bigeye-incidents", at: <iso8601>, note: "grouped with <list>" }` (or `note: "closed with <label>"` for close mode) to `state.json.issues[<display>].actions`.
- For the close mode, also update `status_when_last_seen = "CLOSED"`.

Then run pruning per Step 8.C.

## Errors

| Condition | Behavior |
|---|---|
| Display-name unresolved | print MCP error verbatim per Step 7.D |
| MCP off + create/auto | hard-fail per Step 7.B |
| Update-issue CLI error | print stderr per Step 7.D; do not write state |
| Single ID for merge mode | print `Need at least 2 issue IDs to create a new incident.` and stop |
