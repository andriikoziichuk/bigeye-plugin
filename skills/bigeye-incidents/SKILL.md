---
name: bigeye-incidents
description: Use when the user wants to group related BigEye issues into incidents, merge issues, manage existing incidents, or auto-detect issue clusters
user-invocable: true
---

# BigEye Incident Management

Group related issues into incidents, manage existing incidents, and auto-detect issue clusters.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for status mapping and output formatting, and `skills/bigeye/references/scope.md` for how to load and apply the active scope profile, and skills/bigeye/references/cli.md for CLI invocation rules and MCP-availability detection.

<HARD-GATE>
NEVER create or modify incidents without showing the plan and receiving explicit user confirmation.
Incidents affect issue visibility and tracking in the BigEye UI for the entire team.
</HARD-GATE>

## Arguments

Parse `$ARGUMENTS`:
- `{id1} {id2} {id3}`: merge these specific issues (display names) into a new incident
- `auto`: auto-detect clusters from open issues and suggest groupings
- `add {id} to {incident_id}`: add an issue to an existing incident
- `close {id} --label {label}`: close an incident with a closing label
- `--internal-id`: treat all numeric arguments in this invocation as internal IDs instead of display names. Required when MCP is unavailable (display-name lookup needs MCP).

## Procedure

### Step 0: Load Scope

Follow `skills/bigeye/references/scope.md` (Steps A–E) to load the active profile. Parse `--profile <name>`, `--no-scope`, and `--workspace <id>` from `$ARGUMENTS` before parsing the skill's own arguments. Then follow cli.md Step B to detect MCP availability (sets MCP_AVAILABLE).

For incidents:
- `auto` mode: scope filters the `list_issues` call and the auto-cluster detection — only in-scope issues become candidates.
- Explicit-ID modes (`{id1} {id2} ...`, `add ... to ...`, `close ...`): IDs provided by the user are honored unconditionally (like RCA's primary lookup). Scope does not hide or reject them.

### Mode: Merge Specific Issues (`{id1} {id2} ...`)

**Step 1: Resolve issue IDs**

If `--internal-id` was passed, treat the given number(s) as internal IDs directly.

Otherwise, if `MCP_AVAILABLE=true`:
  Call `mcp__bigeye__search_issues` with `name_query: "{display_name}"` to resolve each display name to an internal ID.

Otherwise (MCP absent and no `--internal-id`):
  Print the `cli.md` Step F warning with `{feature_name}=display-name lookup` and `{CLI-only workaround}=Re-run with --internal-id`. Stop the skill.

Collect internal IDs. If any name doesn't resolve, report it and ask the user to correct.

At least 2 issue IDs are required for a new incident.

**Step 2: Validate relationship**

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=relationship validation` and continue without validation. Skip to Step 3.

If `MCP_AVAILABLE=true`:
  For the first issue, call `mcp__bigeye__list_related_issues` with `starting_issue_id: {first_id}`.
  Check if the other issues appear in the related list.

  If issues are NOT related via lineage, warn the user:
  "These issues don't appear to be related through data lineage. They may still belong to the same incident if they share a common cause. Proceed anyway? (y/n)"

**Step 3: Generate incident name**

Auto-generate a descriptive name from the issues:
- Find the root cause issue (the one with `isRootCause: true` in related issues, or the earliest opened)
- Format: "{dimension} issue affecting {table_name}" or "{root_cause_dimension} cascade from {source_table}"

**Step 4: Present plan and confirm**

```
Scope: {per scope.md Step G}

## Create Incident — "{generated_name}"

Issues to merge:
| Issue | Dimension | Table | Column | Status | Root Cause? |
|-------|-----------|-------|--------|--------|-------------|
| {display_name} | {dim} | {table} | {col} | {status} | {yes/no} |

Proceed? (y/n/edit name)
```

Wait for confirmation.

**Step 5: Create incident**

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=incident creation`. Stop — no CLI equivalent exists.

Call `mcp__bigeye__create_incident` with:
- `issue_ids: [{internal_id_1}, {internal_id_2}, ...]`
- `incident_name: "{generated_name}"`

**Step 6: Report result**

```
## Incident Created — "{name}"

Issues merged:
- #{display_name_1} (root cause) — {description}
- #{display_name_2} — {description}

Root cause: #{root_cause_display_name} (flagged by lineage)
Downstream impact: {related_count} issues

-> Deep dive: `/bigeye-rca {root_cause_display_name}`
-> Acknowledge all issues in this incident
```

### Mode: Auto-Detect (`auto`)

**Step 1: Fetch open issues**

Use CLI per `cli.md` Step C:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> issues get-issues \
  {if data_source_ids non-empty: for each id, append `-wid <id>`} \
  {if schema_names non-empty: for each name, append `-sn <name>`} \
  -op "$TMPDIR"
```

Read each JSON file in `$TMPDIR`; filter in-memory to `status in {ISSUE_STATUS_NEW, ISSUE_STATUS_ACKNOWLEDGED}`; cap at 50.

**Step 2: Build relationship graph**

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=cluster auto-detection`. Stop — *"Cannot auto-detect clusters without MCP — see bigeye-mcp-install.md."*

If `MCP_AVAILABLE=true`:
  For each issue, call `mcp__bigeye__list_related_issues` with `starting_issue_id: {id}`.

  Build clusters: group issues that share any related issue. Two issues are in the same cluster if they share at least one related issue (transitive closure).

**Step 3: Present suggested clusters**

```
Scope: {per scope.md Step G}

## Auto-Detected Issue Clusters

### Cluster 1: "{auto_name}" ({count} issues)
| Issue | Dimension | Table | Root Cause? |
|-------|-----------|-------|-------------|
| ... | ... | ... | ... |

### Cluster 2: "{auto_name}" ({count} issues)
| Issue | Dimension | Table | Root Cause? |
|-------|-----------|-------|-------------|

{count_unclustered} issues have no detected relationships (not shown).

Create incidents for these clusters? (all/1,2/none)
```

- `all`: create incidents for all clusters
- `1,2`: create incidents for specified cluster numbers
- `none`: cancel

**Step 4:** For each confirmed cluster, follow Steps 3-6 from the "Merge Specific Issues" mode above.

### Mode: Add to Existing (`add {id} to {incident_id}`)

1. Resolve both display names to internal IDs:

   If `--internal-id` was passed, treat the given number(s) as internal IDs directly.

   Otherwise, if `MCP_AVAILABLE=true`:
     Call `mcp__bigeye__search_issues` with `name_query: "{display_name}"` to resolve each display name to an internal ID.

   Otherwise (MCP absent and no `--internal-id`):
     Print the `cli.md` Step F warning with `{feature_name}=display-name lookup` and `{CLI-only workaround}=Re-run with --internal-id`. Stop the skill.

2. If `MCP_AVAILABLE=false`:
     Print the `cli.md` Step F warning with `{feature_name}=incident creation`. Stop — no CLI equivalent exists.

   Call `mcp__bigeye__create_incident` with `issue_ids: [{issue_id}]`, `existing_incident_id: {incident_internal_id}`
3. Report result

### Mode: Close (`close {id} --label {label}`)

1. If `--internal-id` was passed, treat `{id}` as internal ID directly. Otherwise resolve via MCP `search_issues` (MCP required — hard-fail with the standard warning if absent).
2. Map the shorthand label to the CLI label (see `conventions.md` Closing Labels section):
   - `--label true-negative` → `TRUE_POSITIVE`
   - `--label false-positive` → `FALSE_POSITIVE`
   - `--label expected` → `EXPECTED`
3. Invoke CLI:
   ```bash
   bigeye -w <profile> issues update-issue \
     -iid <internal_id> \
     -status CLOSED \
     -cl <mapped_label>
   ```
4. On non-zero exit, follow `cli.md` Step G. On success, print:
   ```
   Issue #<display_or_internal_id> closed with label <mapped_label>.
   ```
