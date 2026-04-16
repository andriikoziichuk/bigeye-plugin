# BigEye Scope Configuration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each user configure persistent, per-user scope (workspace + optional filters by data source, table, schema, tag) via named profiles and a `/bigeye-config` wizard, and have every BigEye skill apply that scope automatically with an explicit `Scope:` header in its output.

**Architecture:** One new user-invocable skill (`bigeye-config`) owns the profiles file at `~/.claude/bigeye-plugin/profiles.json`. One new shared reference (`skills/bigeye/references/scope.md`) teaches every other skill how to load a profile, map fields to MCP parameters, and honor override flags. The five existing skills plus the morning-report agent each get small, mechanical edits: read `scope.md` in addition to `conventions.md`, add a "Load scope" step, and print a `Scope:` line as the first output line.

**Tech Stack:** Markdown skill files only. No source code, no test framework. Each task's "verification" is either (a) confirming the file content matches the plan via `Read` / `Grep`, or (b) invoking the slash command manually (covered in Task 11). Commits happen after each task completes.

**Spec reference:** `docs/superpowers/specs/2026-04-16-bigeye-scope-config-design.md`

---

## File Structure

**New files:**
- `skills/bigeye-config/SKILL.md` — the `/bigeye-config` wizard + CRUD skill.
- `skills/bigeye/references/scope.md` — shared scope-loading reference that every other skill reads.

**Modified files:**
- `skills/bigeye/SKILL.md` — add `bigeye-config` to the router table.
- `skills/bigeye-triage/SKILL.md`
- `skills/bigeye-rca/SKILL.md`
- `skills/bigeye-coverage/SKILL.md`
- `skills/bigeye-deploy/SKILL.md`
- `skills/bigeye-incidents/SKILL.md`
- `agents/bigeye-morning-report.md`
- `README.md` — add `/bigeye-config` to the commands table.

**No test files created** — this plugin has no automated tests. Manual verification is Task 11.

**Order rationale:** Tasks 1 and 2 create the foundation (skill + reference). Task 3 wires the router so `/bigeye-config` is reachable. Tasks 4–9 update each skill/agent to consume scope. Task 10 updates the README. Task 11 is the manual verification checklist the user runs themselves.

---

## Task 1: Create the `bigeye-config` skill

**Files:**
- Create: `skills/bigeye-config/SKILL.md`

- [ ] **Step 1: Create the skill directory**

Run:
```bash
mkdir -p /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-config
```

- [ ] **Step 2: Write `skills/bigeye-config/SKILL.md`**

Create the file with exactly this content:

````markdown
---
name: bigeye-config
description: Use when the user wants to configure the BigEye plugin's scope (workspace + filters), run the first-run wizard, or manage named profiles. Also auto-invoked by other BigEye skills when the config file is missing.
user-invocable: true
---

# BigEye Configuration

Owns the per-user profiles file at `~/.claude/bigeye-plugin/profiles.json`. This is the **only** skill that writes to that file.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for shared output formatting.

## Arguments

Parse `$ARGUMENTS` (space-separated). First token is the subcommand; anything after is arguments to that subcommand.

| Invocation | Behavior |
|---|---|
| (empty) or `show` | Print active profile name + all profiles in a table |
| `init` | Run wizard, write a profile, set as default. If a file already exists, ask whether to overwrite or add |
| `add <name>` | Run wizard, add a new profile without changing the default |
| `switch <name>` | Set `default_profile` to `<name>` |
| `edit <name>` | Re-run wizard against an existing profile |
| `delete <name>` | Remove a profile. Refuse if it is the default and no alternative exists |

## Config File

**Path:** `~/.claude/bigeye-plugin/profiles.json`

**Schema:**

```json
{
  "default_profile": "work-area",
  "profiles": {
    "work-area": {
      "workspace_id": 42,
      "data_source_ids": [17],
      "table_ids": [],
      "table_names": ["orders_main", "orders_virtual_recent"],
      "schema_names": [],
      "tags": []
    }
  }
}
```

**Field rules:**
- `default_profile` must reference a key in `profiles`.
- Each profile requires `workspace_id`. All other fields are optional arrays.
- Missing filter fields default to empty arrays when written.

## Procedure

### Subcommand: `show` (or no argument)

1. Use the `Read` tool to read `~/.claude/bigeye-plugin/profiles.json`. If the file doesn't exist, print:
   ```
   No BigEye profiles configured yet.
   Run `/bigeye-config init` to set one up.
   ```
   and stop.
2. Parse the JSON.
3. Print:
   ```
   ## BigEye Profiles

   Active (default): **{default_profile}**

   | Profile | Workspace | Sources | Tables | Schemas | Tags |
   |---------|-----------|---------|--------|---------|------|
   | {name} | {workspace_id} | {count} | {count} | {count} | {count} |
   ```
   One row per profile. Counts are the lengths of the corresponding arrays.

### Subcommand: `init`

1. Use the `Read` tool to check whether `~/.claude/bigeye-plugin/profiles.json` already exists.
2. If it exists, ask:
   ```
   A config file already exists. What would you like to do?
   1. Overwrite with a new default profile
   2. Add a new profile alongside the existing ones (same as `/bigeye-config add <name>`)
   3. Cancel
   ```
   - Option 1 → continue the wizard, then replace the file entirely with a single profile marked default.
   - Option 2 → ask for a profile name, then continue as in `add`.
   - Option 3 → stop.
3. If it does not exist, ask: "What would you like to name this profile? (default: `work-area`)" and use the answer as the profile name.
4. Run the **Wizard Flow** below to fill in fields.
5. Ensure the directory exists using the `Bash` tool:
   ```
   mkdir -p ~/.claude/bigeye-plugin
   ```
6. Use the `Write` tool to write `~/.claude/bigeye-plugin/profiles.json` with the final content.
7. Print:
   ```
   Wrote profile `{name}` to ~/.claude/bigeye-plugin/profiles.json (set as default).
   Try `/bigeye-triage` to see scoped issues.
   ```

### Subcommand: `add <name>`

1. Read the existing file. If it's missing, tell the user to run `/bigeye-config init` first and stop.
2. Run the Wizard Flow for the new profile.
3. Merge the new profile into `profiles` without changing `default_profile`.
4. Write the file.
5. Print confirmation.

### Subcommand: `switch <name>`

1. Read the file. If missing, tell the user to run `/bigeye-config init` first.
2. If `<name>` is not a key in `profiles`, print available profiles and ask the user to pick one. Stop without writing.
3. Update `default_profile` to `<name>` and write the file.
4. Print: `Switched default profile to \`{name}\`.`

### Subcommand: `edit <name>`

1. Read the file. If missing or `<name>` not in `profiles`, error as in `switch`.
2. Show the current profile values.
3. Run the Wizard Flow, pre-filling defaults from the current values (let the user press enter to keep each one).
4. Replace the profile in place. Do not change `default_profile`.
5. Write the file and print confirmation.

### Subcommand: `delete <name>`

1. Read the file. If missing or `<name>` not in `profiles`, error as above.
2. If `<name>` is the `default_profile` and there is only one profile, refuse: "Cannot delete the only profile. Run `/bigeye-config add <new>` first, then delete this one." Stop.
3. If `<name>` is the `default_profile` but other profiles exist, ask which profile to promote as the new default.
4. Remove the profile from `profiles` and update `default_profile` if needed.
5. Write the file and print confirmation.

## Wizard Flow

Ask one question at a time. Show the running summary after each answer.

1. **Workspace ID.** Ask: "What's your BigEye workspace_id? (integer)" Validate that the answer parses as an integer. Optionally, if the `mcp__bigeye__list_data_sources` tool is available, call it with `workspace_id: {answer}` to confirm the workspace is reachable — if it errors, warn the user but allow them to proceed.
2. **Data sources.** Ask: "Filter by data source? (y/n)" If yes, call `mcp__bigeye__list_data_sources` with the chosen `workspace_id`, show the result as a numbered list, and let the user pick one or more by index. Store the chosen integer IDs in `data_source_ids`.
3. **Tables.** Ask: "Filter by specific tables? (y/n)" If yes, ask for one name per line (blank line to finish). For each name, attempt to resolve it to a table ID using whichever of these MCP tools is available, in order: `mcp__bigeye-knowledgebase__search_metadata`, `mcp__bigeye__list_tables` (if present), else skip resolution. Store the original names in `table_names` and any resolved IDs in `table_ids`. Warn about unresolved names but don't block.
4. **Schemas.** Ask: "Filter by schema? (y/n)" If yes, ask for schema names (one per line). Store in `schema_names`.
5. **Tags.** Ask: "Filter by tags? (y/n)" If yes, ask for tag names (one per line). Store in `tags`.
6. **Summary and confirmation.** Show:
   ```
   Profile summary:
     workspace_id: {...}
     data_source_ids: [...]
     table_names: [...]
     table_ids: [...]
     schema_names: [...]
     tags: [...]

   Save this profile? (y/n)
   ```
   On `n`, restart the wizard. On `y`, continue to the caller's write step.

## Notes

- Always pretty-print JSON with 2-space indent when writing.
- Never include comments in the JSON file.
- When reading the file, handle `FileNotFoundError` by treating it as "no config yet."
- When the JSON fails to parse, print the parse error and suggest `/bigeye-config init` to recreate.
````

- [ ] **Step 3: Verify the file was written with the expected structure**

Run:
```bash
wc -l /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-config/SKILL.md
```
Expected: at least 100 lines.

Run a grep to confirm each subcommand is documented:
Use the `Grep` tool with pattern `^### Subcommand:` and path `skills/bigeye-config/SKILL.md`. Expected: 6 matches (`show`, `init`, `add`, `switch`, `edit`, `delete`).

- [ ] **Step 4: Commit**

Run:
```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && \
git add skills/bigeye-config/SKILL.md && \
git commit -m "Add bigeye-config skill for scope profile management

Owns ~/.claude/bigeye-plugin/profiles.json. Provides show / init / add /
switch / edit / delete subcommands plus a guided wizard."
```

---

## Task 2: Create the shared `scope.md` reference

**Files:**
- Create: `skills/bigeye/references/scope.md`

- [ ] **Step 1: Write `skills/bigeye/references/scope.md`**

Create the file with exactly this content:

````markdown
# BigEye Plugin — Scope Loading

All BigEye skills MUST follow this document in addition to `conventions.md` to load and apply the user's active scope profile before performing any BigEye MCP calls.

---

## Step A: Locate the Config File

Path: `~/.claude/bigeye-plugin/profiles.json`

Use the `Read` tool. If the file is missing:
1. Invoke the `bigeye-config` skill with argument `init` (via the `Skill` tool).
2. After it completes, re-read the file.
3. If still missing (user cancelled the wizard), stop the current skill and print: `Aborted — no scope profile configured.`

If the JSON fails to parse:
Stop the current skill. Print:
```
Scope config at ~/.claude/bigeye-plugin/profiles.json is malformed:
{parse error}

Run `/bigeye-config init` to recreate it.
```

## Step B: Select the Active Profile

1. Parse `$ARGUMENTS` for these flags (in addition to each skill's own arguments). Remove them from the argument list before the skill processes its own args:
   - `--profile <name>`
   - `--no-scope`
   - `--workspace <id>` (integer)
2. If `--profile <name>` was given, use `profiles[<name>]`. If that key does not exist, stop and print:
   ```
   Profile `<name>` not found. Available profiles: {list}.
   ```
3. Otherwise, use `profiles[default_profile]`. If `default_profile` points to a missing key, stop and print:
   ```
   default_profile `<name>` does not exist in profiles. Available: {list}.
   Run `/bigeye-config switch <name>` to pick a valid default.
   ```
4. If the chosen profile is missing `workspace_id`, stop and print:
   ```
   Profile `<name>` has no workspace_id. Run `/bigeye-config edit <name>` to fix it.
   ```

## Step C: Apply Override Flags

- `--workspace <id>` replaces `workspace_id` in the working profile.
- `--no-scope` clears `data_source_ids`, `table_ids`, `table_names`, `schema_names`, and `tags` in the working profile (workspace_id stays).
- `--profile` only affected *which* profile was loaded in Step B; no further action here.

These flags compose: a command may combine any of them.

## Step D: Resolve Table Names to IDs (once)

If the working profile has non-empty `table_names`:
1. For each name, attempt to resolve it using whichever of these MCP tools is available, in order:
   - `mcp__bigeye-knowledgebase__search_metadata`
   - `mcp__bigeye__list_tables` (or equivalent)
2. Union the resolved IDs with `table_ids`.
3. Track unresolved names for the Scope header.

Do this **once** per invocation — not before every MCP call.

## Step E: Build the MCP Parameter Map

When calling `mcp__bigeye__list_issues` or any tool that accepts these parameters, include only the non-empty fields from the working profile:

| Profile field | MCP parameter name |
|---|---|
| `workspace_id` | `workspace_id` |
| `data_source_ids` | `data_source_ids` (if the MCP tool instead uses `source_ids`, use that name — pick whichever the tool's schema accepts) |
| `table_ids` (including resolved table_names) | `table_ids` |
| `schema_names` | `schema_names` |
| `tags` | `tags` |

Omit any parameter whose field is empty.

## Step F: Per-Skill Applicability

| Skill | Apply scope to |
|---|---|
| `bigeye-triage` | The `list_issues` call — fully scoped |
| `bigeye-coverage` | Table enumeration — only scan in-scope tables |
| `bigeye-deploy` | Default to in-scope tables unless the user names a specific target explicitly |
| `bigeye-incidents` | Issue listing + auto-cluster detection — fully scoped |
| `bigeye-rca` | Primary issue lookup (by ID) is **unscoped**. Scope applies only to lineage expansion and related-issue search |
| `bigeye-morning-report` (agent) | Same as triage — fully scoped |

## Step G: Print the Scope Header

Every skill's output MUST start with a single line `Scope:` header before any other content.

**Normal case:**
```
Scope: profile={name} · workspace={id} · sources={count} · tables={count} · schemas={count} · tags={count}
```

Omit any facet that is zero. Example with nothing set: `Scope: profile=full-view · workspace=42`

**With `--no-scope`:**
```
Scope: profile={name} · workspace={id} · NO-SCOPE (override)
```

**With unresolved table names:**
```
Scope: profile={name} · workspace={id} · tables=2/3 (unresolved: "orders_virtual_ltv") · sources=1
```

## Step H: Empty-Result Phrasing

When a scoped BigEye call returns zero items, the skill's output MUST distinguish scoped emptiness from generic emptiness:

- If scope filters were applied: `No active issues in scope '{profile}' — all clear.`
- If `--no-scope` was used: `No active issues — all clear.`

## Step I: Out-of-Scope RCA Soft Notice

Specific to `bigeye-rca`: if the user asks to investigate an issue by ID, fetch and analyze it unconditionally. Then, if the issue's table/data_source is outside the working profile's scope, print immediately after the `Scope:` header:

```
Note: issue {display_name} is outside the current scope '{profile}'.
```

This is informational — never refuse to analyze an explicitly-named issue.
````

- [ ] **Step 2: Verify the file exists and has the expected sections**

Use the `Grep` tool with pattern `^## Step [A-I]:` and path `skills/bigeye/references/scope.md`. Expected: 9 matches (Steps A through I).

- [ ] **Step 3: Commit**

Run:
```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && \
git add skills/bigeye/references/scope.md && \
git commit -m "Add scope.md — shared scope-loading reference for all BigEye skills

Every BigEye skill reads this to resolve the active profile, apply
override flags, map fields to MCP parameters, and print a Scope header."
```

---

## Task 3: Wire `bigeye-config` into the BigEye router

**Files:**
- Modify: `skills/bigeye/SKILL.md`

- [ ] **Step 1: Add the config skill to the Available Skills table**

Use the `Edit` tool on `skills/bigeye/SKILL.md`.

Replace:
```
| Skill | Command | Purpose |
|-------|---------|---------|
| Triage | `/bigeye-triage` | What's on fire? Prioritized active issues |
| Root Cause Analysis | `/bigeye-rca` | Why is this broken? Lineage-traced diagnosis |
| Coverage | `/bigeye-coverage` | What's not monitored? Dimension/column gaps |
| Deploy | `/bigeye-deploy` | Set up monitors with sensible defaults |
| Incidents | `/bigeye-incidents` | Group related issues into incidents |
```

With:
```
| Skill | Command | Purpose |
|-------|---------|---------|
| Config | `/bigeye-config` | Set up workspace + scope profiles (wizard) |
| Triage | `/bigeye-triage` | What's on fire? Prioritized active issues |
| Root Cause Analysis | `/bigeye-rca` | Why is this broken? Lineage-traced diagnosis |
| Coverage | `/bigeye-coverage` | What's not monitored? Dimension/column gaps |
| Deploy | `/bigeye-deploy` | Set up monitors with sensible defaults |
| Incidents | `/bigeye-incidents` | Group related issues into incidents |
```

- [ ] **Step 2: Add a routing row for config intents**

Use the `Edit` tool on `skills/bigeye/SKILL.md`.

Replace:
```
| User intent | Invoke |
|-------------|--------|
| "what's broken?", "show active issues", "what's on fire", "triage", "status" | Skill: `bigeye-triage` |
```

With:
```
| User intent | Invoke |
|-------------|--------|
| "set up", "configure", "change workspace", "switch profile", "first run" | Skill: `bigeye-config` |
| "what's broken?", "show active issues", "what's on fire", "triage", "status" | Skill: `bigeye-triage` |
```

- [ ] **Step 3: Update the "Before doing anything else" line**

Use the `Edit` tool on `skills/bigeye/SKILL.md`.

Replace:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for shared formatting and severity rules.
```

With:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for shared formatting and severity rules, and `skills/bigeye/references/scope.md` for how to apply the user's active scope profile.
```

- [ ] **Step 4: Update the ambiguous-intent menu**

Use the `Edit` tool on `skills/bigeye/SKILL.md`.

Replace:
```
1. **Triage** — See active issues prioritized by severity (`/bigeye-triage`)
2. **Root Cause Analysis** — Trace why an issue is happening (`/bigeye-rca`)
3. **Coverage** — Find monitoring gaps (`/bigeye-coverage`)
4. **Deploy Monitors** — Set up new monitors (`/bigeye-deploy`)
5. **Incidents** — Group related issues (`/bigeye-incidents`)
```

With:
```
1. **Config** — Set up or switch scope profiles (`/bigeye-config`)
2. **Triage** — See active issues prioritized by severity (`/bigeye-triage`)
3. **Root Cause Analysis** — Trace why an issue is happening (`/bigeye-rca`)
4. **Coverage** — Find monitoring gaps (`/bigeye-coverage`)
5. **Deploy Monitors** — Set up new monitors (`/bigeye-deploy`)
6. **Incidents** — Group related issues (`/bigeye-incidents`)
```

- [ ] **Step 5: Verify all edits landed**

Use the `Grep` tool with pattern `bigeye-config` and path `skills/bigeye/SKILL.md`. Expected: at least 3 matches (Available Skills, Routing, Ambiguous Intent).

- [ ] **Step 6: Commit**

Run:
```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && \
git add skills/bigeye/SKILL.md && \
git commit -m "Wire bigeye-config into the bigeye router

Routes setup/configure intents to the config skill and teaches the router
to read scope.md for profile application."
```

---

## Task 4: Wire scope into `bigeye-triage`

**Files:**
- Modify: `skills/bigeye-triage/SKILL.md`

- [ ] **Step 1: Update the "Before doing anything else" line**

Use the `Edit` tool on `skills/bigeye-triage/SKILL.md`.

Replace:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for severity classification rules and output formatting.
```

With:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for severity classification rules and output formatting, and `skills/bigeye/references/scope.md` for how to load and apply the active scope profile.
```

- [ ] **Step 2: Add a new "Step 0: Load Scope" section**

Use the `Edit` tool on `skills/bigeye-triage/SKILL.md`.

Replace:
```
## Procedure

### Step 1: Fetch Active Issues
```

With:
```
## Procedure

### Step 0: Load Scope

Follow `skills/bigeye/references/scope.md` (Steps A–E) to load the active profile and build the parameter map. Parse and honor `--profile <name>`, `--no-scope`, and `--workspace <id>` flags from `$ARGUMENTS` before parsing the skill's own arguments.

### Step 1: Fetch Active Issues
```

- [ ] **Step 3: Inject scope parameters into the `list_issues` call**

Use the `Edit` tool on `skills/bigeye-triage/SKILL.md`.

Replace:
```
Call `mcp__bigeye__list_issues` with:
- `statuses`: `["ISSUE_STATUS_NEW", "ISSUE_STATUS_ACKNOWLEDGED"]`
  - If argument is `new`, use only `["ISSUE_STATUS_NEW"]`
- `compact`: `false` (we need metric info for severity classification)
- `max_issues`: `50` (or user-specified override)
```

With:
```
Call `mcp__bigeye__list_issues` with:
- `statuses`: `["ISSUE_STATUS_NEW", "ISSUE_STATUS_ACKNOWLEDGED"]`
  - If argument is `new`, use only `["ISSUE_STATUS_NEW"]`
- `compact`: `false` (we need metric info for severity classification)
- `max_issues`: `50` (or user-specified override)
- Plus every non-empty scope parameter from the Step 0 map (`workspace_id`, `data_source_ids`, `table_ids`, `schema_names`, `tags`).
```

- [ ] **Step 4: Inject the `Scope:` header and fix the empty-result phrasing**

Use the `Edit` tool on `skills/bigeye-triage/SKILL.md`.

Replace:
```
If no issues returned, report "No active issues — all clear." and stop.
```

With:
```
If no issues returned, print the empty-result message per scope.md Step H (`No active issues in scope '{profile}' — all clear.` or `No active issues — all clear.` under `--no-scope`) and stop.
```

- [ ] **Step 5: Prepend the `Scope:` header to the output format**

Use the `Edit` tool on `skills/bigeye-triage/SKILL.md`.

Replace:
```
```
## BigEye Triage — {today's date}

### Critical ({count} issues)
```

With:
```
```
Scope: {per scope.md Step G}

## BigEye Triage — {today's date}

### Critical ({count} issues)
```

- [ ] **Step 6: Verify all edits landed**

Use the `Grep` tool with pattern `scope\.md` and path `skills/bigeye-triage/SKILL.md`. Expected: at least 3 matches.

Use the `Grep` tool with pattern `Step 0: Load Scope` and path `skills/bigeye-triage/SKILL.md`. Expected: 1 match.

- [ ] **Step 7: Commit**

Run:
```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && \
git add skills/bigeye-triage/SKILL.md && \
git commit -m "Wire scope into bigeye-triage

Adds Step 0 (Load Scope), threads workspace/filter params through the
list_issues call, and prepends the Scope header to output."
```

---

## Task 5: Wire scope into `bigeye-rca` (with RCA-specific rules)

**Files:**
- Modify: `skills/bigeye-rca/SKILL.md`

- [ ] **Step 1: Update the "Before doing anything else" line**

Use the `Edit` tool on `skills/bigeye-rca/SKILL.md`.

Replace:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for severity classification and output formatting.
```

With:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for severity classification and output formatting, and `skills/bigeye/references/scope.md` for how to load and apply the active scope profile.

**RCA special case:** primary issue lookup by ID is ALWAYS unscoped (the user named a specific issue). Scope applies only to the lineage expansion and related-issue search in Steps 3–4. See scope.md Step I for the out-of-scope soft-notice text.
```

- [ ] **Step 2: Insert "Step 0: Load Scope"**

Use the `Edit` tool on `skills/bigeye-rca/SKILL.md`.

Replace:
```
## Procedure

### Step 1: Resolve the Issue
```

With:
```
## Procedure

### Step 0: Load Scope

Follow `skills/bigeye/references/scope.md` (Steps A–E) to load the active profile. Parse `--profile <name>`, `--no-scope`, and `--workspace <id>` from `$ARGUMENTS` before parsing the skill's own arguments.

RCA reminder: the primary issue lookup in Step 1 ignores scope. Scope applies to Steps 3 (lineage expansion) and 4 (related issues only).

### Step 1: Resolve the Issue
```

- [ ] **Step 3: Apply scope to lineage trace (Step 3)**

Use the `Edit` tool on `skills/bigeye-rca/SKILL.md`.

Replace:
```
Call `mcp__bigeye__get_issue_lineage_trace` with:
- `issue_id: {internal_id}`
- `include_root_cause_analysis: true`
- `include_impact_analysis: true`
- `max_depth: 5`
```

With:
```
Call `mcp__bigeye__get_issue_lineage_trace` with:
- `issue_id: {internal_id}`
- `include_root_cause_analysis: true`
- `include_impact_analysis: true`
- `max_depth: 5`
- Plus non-empty scope parameters from Step 0 if the tool's schema accepts them; otherwise post-filter the returned nodes/edges to the in-scope tables only.
```

- [ ] **Step 4: Apply scope to related-issues search (Step 4)**

Use the `Edit` tool on `skills/bigeye-rca/SKILL.md`.

Replace:
```
Call `mcp__bigeye__list_related_issues` with `starting_issue_id: {internal_id}`.

Note which related issues have `isRootCause: true`.
```

With:
```
Call `mcp__bigeye__list_related_issues` with `starting_issue_id: {internal_id}`.

Filter the returned list to only include issues whose table/data_source falls inside the working profile (per Step 0 map). Do not apply this filter under `--no-scope`.

Note which related issues have `isRootCause: true`.
```

- [ ] **Step 5: Prepend the Scope header (and soft notice) to the output format**

Use the `Edit` tool on `skills/bigeye-rca/SKILL.md`.

Replace:
```
```
## Root Cause Analysis — Issue #{display_name}

### Issue
```

With:
```
```
Scope: {per scope.md Step G}
{If the primary issue is outside the working scope, insert the soft notice from scope.md Step I on the next line.}

## Root Cause Analysis — Issue #{display_name}

### Issue
```

- [ ] **Step 6: Verify all edits landed**

Use the `Grep` tool with pattern `scope\.md` and path `skills/bigeye-rca/SKILL.md`. Expected: at least 4 matches.

Use the `Grep` tool with pattern `Step 0: Load Scope` and path `skills/bigeye-rca/SKILL.md`. Expected: 1 match.

- [ ] **Step 7: Commit**

Run:
```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && \
git add skills/bigeye-rca/SKILL.md && \
git commit -m "Wire scope into bigeye-rca

Primary issue lookup stays unscoped; lineage expansion and related-issue
search are filtered to the working profile. Adds out-of-scope soft notice."
```

---

## Task 6: Wire scope into `bigeye-coverage`

**Files:**
- Modify: `skills/bigeye-coverage/SKILL.md`

- [ ] **Step 1: Update the "Before doing anything else" line**

Use the `Edit` tool on `skills/bigeye-coverage/SKILL.md`.

Replace:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for output formatting and severity rules.
```

With:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for output formatting and severity rules, and `skills/bigeye/references/scope.md` for how to load and apply the active scope profile.
```

- [ ] **Step 2: Insert "Step 0: Load Scope"**

Use the `Edit` tool on `skills/bigeye-coverage/SKILL.md`.

Replace:
```
## Procedure

### Step 1: Get Table Dimension Coverage

Call `mcp__bigeye__get_table_dimension_coverage` with `table_name: "{table_name}"`.

If the table name is unknown, call `mcp__bigeye__list_data_sources` first to discover available tables, then ask the user which table to analyze.
```

With:
```
## Procedure

### Step 0: Load Scope

Follow `skills/bigeye/references/scope.md` (Steps A–E) to load the active profile. Parse `--profile <name>`, `--no-scope`, and `--workspace <id>` from `$ARGUMENTS` before parsing the skill's own arguments.

For coverage, the scope determines which tables to enumerate:
- If the profile has non-empty `table_ids` / `table_names`, those are the tables to report on (iterate over each).
- Otherwise, if `data_source_ids` is non-empty, enumerate tables within those sources and filter to the working profile.
- Otherwise, fall back to the existing behavior (ask the user for a table name).

### Step 1: Get Table Dimension Coverage

Call `mcp__bigeye__get_table_dimension_coverage` with `table_name: "{table_name}"` for each in-scope table.

If no in-scope tables are known (empty profile under `--no-scope`), call `mcp__bigeye__list_data_sources` first to discover available tables, then ask the user which table to analyze.
```

- [ ] **Step 3: Scope the table-issues lookup (Step 4)**

Use the `Edit` tool on `skills/bigeye-coverage/SKILL.md`.

Replace:
```
For gap prioritization, fetch past issues:
Call `mcp__bigeye__list_table_issues` with:
- `table_name: "{table_name}"`
- `statuses: ["ISSUE_STATUS_NEW", "ISSUE_STATUS_ACKNOWLEDGED", "ISSUE_STATUS_CLOSED"]`
```

With:
```
For gap prioritization, fetch past issues:
Call `mcp__bigeye__list_table_issues` with:
- `table_name: "{table_name}"`
- `statuses: ["ISSUE_STATUS_NEW", "ISSUE_STATUS_ACKNOWLEDGED", "ISSUE_STATUS_CLOSED"]`
- Plus `workspace_id` from the Step 0 map.
```

- [ ] **Step 4: Prepend the Scope header to the output**

Use the `Edit` tool on `skills/bigeye-coverage/SKILL.md`.

Replace:
```
```
## Coverage Report — {schema}.{table_name}

### Overall Score: {percent}% ({covered} of {total} dimension-column pairs covered)
```

With:
```
```
Scope: {per scope.md Step G}

## Coverage Report — {schema}.{table_name}

### Overall Score: {percent}% ({covered} of {total} dimension-column pairs covered)
```

- [ ] **Step 5: Verify all edits landed**

Use the `Grep` tool with pattern `scope\.md` and path `skills/bigeye-coverage/SKILL.md`. Expected: at least 3 matches.

- [ ] **Step 6: Commit**

Run:
```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && \
git add skills/bigeye-coverage/SKILL.md && \
git commit -m "Wire scope into bigeye-coverage

Enumerates only in-scope tables and threads workspace_id into the
table-issues lookup. Adds the Scope header."
```

---

## Task 7: Wire scope into `bigeye-deploy`

**Files:**
- Modify: `skills/bigeye-deploy/SKILL.md`

- [ ] **Step 1: Update the "Before doing anything else" line**

Use the `Edit` tool on `skills/bigeye-deploy/SKILL.md`.

Replace:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for tag conventions, output formatting, and defaults.
```

With:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for tag conventions, output formatting, and defaults, and `skills/bigeye/references/scope.md` for how to load and apply the active scope profile.
```

- [ ] **Step 2: Insert "Step 0: Load Scope"**

Use the `Edit` tool on `skills/bigeye-deploy/SKILL.md`.

Replace:
```
## Procedure

### Step 1: Build Deployment Plan
```

With:
```
## Procedure

### Step 0: Load Scope

Follow `skills/bigeye/references/scope.md` (Steps A–E) to load the active profile. Parse `--profile <name>`, `--no-scope`, and `--workspace <id>` from `$ARGUMENTS` before parsing the skill's own arguments.

For deploy:
- If the user named a specific target (`columns {cols}`, `freshness`, `bulk {dim}` against a named table), the scope's table filter does NOT restrict the target — the user's explicit target wins.
- If the user said `gaps`, deploy only to in-scope tables (iterate over each table from the working profile).

### Step 1: Build Deployment Plan
```

- [ ] **Step 3: Thread `workspace_id` into `create_metric` calls**

Use the `Edit` tool on `skills/bigeye-deploy/SKILL.md`.

Replace:
```
For each row in the confirmed plan, call `mcp__bigeye__create_metric` with:
- `table_name: "{table_name}"`
- `metric_type: "{metric_type}"`
- `column_name: "{column}"` (omit for table-level metrics like FRESHNESS, COUNT_ROWS)
- `lookback_type: "DATA_TIME"`
- `lookback_interval_type: "DAYS"`
- `lookback_interval_value: 7` (or user-specified)
- `schema_name: "{schema}"` (if known)
```

With:
```
For each row in the confirmed plan, call `mcp__bigeye__create_metric` with:
- `table_name: "{table_name}"`
- `metric_type: "{metric_type}"`
- `column_name: "{column}"` (omit for table-level metrics like FRESHNESS, COUNT_ROWS)
- `lookback_type: "DATA_TIME"`
- `lookback_interval_type: "DAYS"`
- `lookback_interval_value: 7` (or user-specified)
- `schema_name: "{schema}"` (if known)
- `workspace_id` from the Step 0 map (required so the monitor is created in the right workspace).
```

- [ ] **Step 4: Prepend the Scope header to the deployment plan output**

Use the `Edit` tool on `skills/bigeye-deploy/SKILL.md`.

Replace:
```
```
## Deploy Plan — {count} monitors on {table_name}

| # | Column | Metric Type | Dimension | Lookback |
```

With:
```
```
Scope: {per scope.md Step G}

## Deploy Plan — {count} monitors on {table_name}

| # | Column | Metric Type | Dimension | Lookback |
```

- [ ] **Step 5: Verify all edits landed**

Use the `Grep` tool with pattern `scope\.md` and path `skills/bigeye-deploy/SKILL.md`. Expected: at least 3 matches.

- [ ] **Step 6: Commit**

Run:
```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && \
git add skills/bigeye-deploy/SKILL.md && \
git commit -m "Wire scope into bigeye-deploy

Gaps mode iterates over in-scope tables; explicit targets override.
Threads workspace_id into create_metric and adds the Scope header."
```

---

## Task 8: Wire scope into `bigeye-incidents`

**Files:**
- Modify: `skills/bigeye-incidents/SKILL.md`

- [ ] **Step 1: Update the "Before doing anything else" line**

Use the `Edit` tool on `skills/bigeye-incidents/SKILL.md`.

Replace:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for status mapping and output formatting.
```

With:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for status mapping and output formatting, and `skills/bigeye/references/scope.md` for how to load and apply the active scope profile.
```

- [ ] **Step 2: Insert "Step 0: Load Scope"**

Use the `Edit` tool on `skills/bigeye-incidents/SKILL.md`.

Replace:
```
## Procedure

### Mode: Merge Specific Issues (`{id1} {id2} ...`)
```

With:
```
## Procedure

### Step 0: Load Scope

Follow `skills/bigeye/references/scope.md` (Steps A–E) to load the active profile. Parse `--profile <name>`, `--no-scope`, and `--workspace <id>` from `$ARGUMENTS` before parsing the skill's own arguments.

For incidents:
- `auto` mode: scope filters the `list_issues` call and the auto-cluster detection — only in-scope issues become candidates.
- Explicit-ID modes (`{id1} {id2} ...`, `add ... to ...`, `close ...`): IDs provided by the user are honored unconditionally (like RCA's primary lookup). Scope does not hide or reject them.

### Mode: Merge Specific Issues (`{id1} {id2} ...`)
```

- [ ] **Step 3: Thread scope parameters into the auto-mode `list_issues` call**

Use the `Edit` tool on `skills/bigeye-incidents/SKILL.md`.

Replace:
```
**Step 1: Fetch open issues**

Call `mcp__bigeye__list_issues` with:
- `statuses: ["ISSUE_STATUS_NEW", "ISSUE_STATUS_ACKNOWLEDGED"]`
- `compact: false`
- `max_issues: 50`
```

With:
```
**Step 1: Fetch open issues**

Call `mcp__bigeye__list_issues` with:
- `statuses: ["ISSUE_STATUS_NEW", "ISSUE_STATUS_ACKNOWLEDGED"]`
- `compact: false`
- `max_issues: 50`
- Plus every non-empty scope parameter from the Step 0 map (`workspace_id`, `data_source_ids`, `table_ids`, `schema_names`, `tags`).
```

- [ ] **Step 4: Prepend the Scope header to both "Create Incident" and "Auto-Detected Issue Clusters" outputs**

Use the `Edit` tool on `skills/bigeye-incidents/SKILL.md`.

Replace:
```
```
## Create Incident — "{generated_name}"

Issues to merge:
```

With:
```
```
Scope: {per scope.md Step G}

## Create Incident — "{generated_name}"

Issues to merge:
```

Then use the `Edit` tool again on `skills/bigeye-incidents/SKILL.md`.

Replace:
```
```
## Auto-Detected Issue Clusters

### Cluster 1: "{auto_name}" ({count} issues)
```

With:
```
```
Scope: {per scope.md Step G}

## Auto-Detected Issue Clusters

### Cluster 1: "{auto_name}" ({count} issues)
```

- [ ] **Step 5: Verify all edits landed**

Use the `Grep` tool with pattern `scope\.md` and path `skills/bigeye-incidents/SKILL.md`. Expected: at least 3 matches.

Use the `Grep` tool with pattern `^Scope:` and path `skills/bigeye-incidents/SKILL.md`. Expected: 2 matches (both output templates).

- [ ] **Step 6: Commit**

Run:
```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && \
git add skills/bigeye-incidents/SKILL.md && \
git commit -m "Wire scope into bigeye-incidents

Auto mode is scope-filtered; explicit IDs always honored. Scope header
added to both Create Incident and Auto-Detected Clusters outputs."
```

---

## Task 9: Wire scope into the morning-report agent

**Files:**
- Modify: `agents/bigeye-morning-report.md`

- [ ] **Step 1: Update the "Before starting" line**

Use the `Edit` tool on `agents/bigeye-morning-report.md`.

Replace:
```
Before starting, read `skills/bigeye/references/conventions.md` for severity classification, output formatting, and Slack templates.
```

With:
```
Before starting, read `skills/bigeye/references/conventions.md` for severity classification, output formatting, and Slack templates, and `skills/bigeye/references/scope.md` for how to load and apply the active scope profile.
```

- [ ] **Step 2: Insert a "Step 0: Load Scope" before the current Step 1**

Use the `Edit` tool on `agents/bigeye-morning-report.md`.

Replace:
```
## Workflow

Execute these steps in order:

### 1. Triage — Current Issue State

Call `mcp__bigeye__list_issues` with:
- `statuses: ["ISSUE_STATUS_NEW", "ISSUE_STATUS_ACKNOWLEDGED"]`
- `compact: false`
- `max_issues: 50`
```

With:
```
## Workflow

Execute these steps in order:

### 0. Load Scope

Follow `skills/bigeye/references/scope.md` (Steps A–E) to load the active profile. Parse `--profile <name>`, `--no-scope`, and `--workspace <id>` from any agent arguments. If no config file exists (unattended run), stop and print a single line: `Cannot run morning report — no BigEye profile configured. Run \`/bigeye-config init\` once on this machine.` (The agent cannot run the interactive wizard because there is no user present.)

### 1. Triage — Current Issue State

Call `mcp__bigeye__list_issues` with:
- `statuses: ["ISSUE_STATUS_NEW", "ISSUE_STATUS_ACKNOWLEDGED"]`
- `compact: false`
- `max_issues: 50`
- Plus every non-empty scope parameter from the Step 0 map (`workspace_id`, `data_source_ids`, `table_ids`, `schema_names`, `tags`).
```

- [ ] **Step 3: Scope the coverage check (Step 3)**

Use the `Edit` tool on `agents/bigeye-morning-report.md`.

Replace:
```
### 3. Coverage Check

Call `mcp__bigeye__get_table_dimension_coverage` with the monitored table.

Record the overall coverage percentage.
```

With:
```
### 3. Coverage Check

For each in-scope table (from the Step 0 map's `table_ids` / resolved `table_names`), call `mcp__bigeye__get_table_dimension_coverage` with that table.

Record the overall coverage percentage. If multiple tables are in scope, report the average or list them individually (whichever fits within the Slack template).

If the working profile has no tables (empty profile or `--no-scope`), skip this step and report coverage as "n/a (no tables in scope)".
```

- [ ] **Step 4: Prepend the Scope header to the terminal report**

Use the `Edit` tool on `agents/bigeye-morning-report.md`.

Replace:
```
Output this format:

```
## Morning Report — {date} {time}

### Current State
```

With:
```
Output this format:

```
Scope: {per scope.md Step G}

## Morning Report — {date} {time}

### Current State
```

- [ ] **Step 5: Verify all edits landed**

Use the `Grep` tool with pattern `scope\.md` and path `agents/bigeye-morning-report.md`. Expected: at least 3 matches.

- [ ] **Step 6: Commit**

Run:
```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && \
git add agents/bigeye-morning-report.md && \
git commit -m "Wire scope into bigeye-morning-report agent

Scoped list_issues + per-table coverage. Refuses to run unattended
without a configured profile (cannot run the interactive wizard)."
```

---

## Task 10: Update the README commands table

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add `/bigeye-config` to the commands table**

Use the `Edit` tool on `README.md`.

Replace:
```
| Command | Description |
|---------|-------------|
| `/bigeye` | Smart router — describe what you need in natural language |
| `/bigeye-triage` | Prioritized view of active issues |
| `/bigeye-rca [issue#]` | Root cause analysis with lineage tracing |
| `/bigeye-coverage` | Find monitoring gaps across dimensions |
| `/bigeye-deploy [target]` | Deploy monitors with confirmation |
| `/bigeye-incidents [ids/auto]` | Group related issues into incidents |
```

With:
```
| Command | Description |
|---------|-------------|
| `/bigeye` | Smart router — describe what you need in natural language |
| `/bigeye-config [init/show/switch/add/edit/delete]` | Manage scope profiles (workspace + table/source/schema/tag filters) |
| `/bigeye-triage` | Prioritized view of active issues (scope-filtered) |
| `/bigeye-rca [issue#]` | Root cause analysis with lineage tracing |
| `/bigeye-coverage` | Find monitoring gaps across dimensions (scope-filtered) |
| `/bigeye-deploy [target]` | Deploy monitors with confirmation |
| `/bigeye-incidents [ids/auto]` | Group related issues into incidents |
```

- [ ] **Step 2: Update the Configuration section to mention profiles**

Use the `Edit` tool on `README.md`.

Replace:
```
## Configuration

Edit `skills/bigeye/references/conventions.md` to customize:
- Slack channel and mention groups
- Severity classification thresholds
- Output formatting preferences
- Default monitor settings
```

With:
```
## Configuration

**Scope profiles (per-user):** Run `/bigeye-config init` once after installing the plugin. This creates `~/.claude/bigeye-plugin/profiles.json` with your workspace ID and optional filters (data sources, tables, schemas, tags). Every skill applies the active profile automatically; override per-invocation with `--profile <name>`, `--no-scope`, or `--workspace <id>`.

**Shared conventions:** edit `skills/bigeye/references/conventions.md` to customize:
- Slack channel and mention groups
- Severity classification thresholds
- Output formatting preferences
- Default monitor settings
```

- [ ] **Step 3: Verify both edits landed**

Use the `Grep` tool with pattern `bigeye-config` and path `README.md`. Expected: at least 2 matches.

- [ ] **Step 4: Commit**

Run:
```bash
cd /Users/andriik-mbp/PycharmProjects/bigeye-plugin && \
git add README.md && \
git commit -m "README: document /bigeye-config and scope profiles

Adds the new command to the commands table and explains the profiles
file + per-invocation override flags in the Configuration section."
```

---

## Task 11: Manual verification checklist

This task does not modify any files — it's a checklist to execute by hand against a real BigEye workspace, confirming the plan's behavior.

- [ ] **Step 1: Wizard round-trip**

- Before running, back up or remove `~/.claude/bigeye-plugin/profiles.json` so the next step exercises the missing-config path:
  ```bash
  mv ~/.claude/bigeye-plugin/profiles.json ~/.claude/bigeye-plugin/profiles.json.bak 2>/dev/null || true
  ```
- Invoke `/bigeye-triage`. Expected: the skill auto-invokes `bigeye-config init`, walks through the wizard, writes the file, then continues with triage output.
- Confirm the file now exists:
  ```bash
  cat ~/.claude/bigeye-plugin/profiles.json
  ```
  Expected: valid JSON, `default_profile` set, one profile with a valid `workspace_id`.

- [ ] **Step 2: `/bigeye-config show`**

- Invoke `/bigeye-config`. Expected: a table listing the profile name, workspace, and array counts.
- Invoke `/bigeye-config show`. Expected: identical output.

- [ ] **Step 3: Add a second profile and switch between them**

- Invoke `/bigeye-config add full-view`. Walk through the wizard, leaving all filter fields empty.
- Invoke `/bigeye-config show`. Expected: both profiles listed; original still marked default.
- Invoke `/bigeye-config switch full-view`. Expected: `Switched default profile to \`full-view\`.`
- Invoke `/bigeye-config switch work-area` (or whatever the original is called) to switch back.

- [ ] **Step 4: Scope applies to triage**

- Invoke `/bigeye-triage`. Expected first line: `Scope: profile=... · workspace=...`. Issue list should be restricted to in-scope issues only.
- Invoke `/bigeye-triage --no-scope`. Expected first line: `Scope: profile=... · workspace=... · NO-SCOPE (override)`. Issue list should include issues outside the usual scope.
- Invoke `/bigeye-triage --profile full-view`. Expected: full-view's Scope header, not the default's.

- [ ] **Step 5: Scope applies to coverage**

- Invoke `/bigeye-coverage`. Expected: coverage report only for in-scope tables. Scope header present.

- [ ] **Step 6: RCA honors explicit IDs but scopes related-issue search**

- Pick an issue ID that's inside the current scope. Invoke `/bigeye-rca {id}`. Expected: Scope header, normal RCA output, related-issues list restricted to in-scope tables.
- Pick an issue ID that's outside the current scope. Invoke `/bigeye-rca {id}`. Expected: Scope header, soft notice line (`Note: issue {id} is outside the current scope '{profile}'.`), then normal RCA output.

- [ ] **Step 7: Error paths**

- Manually edit `~/.claude/bigeye-plugin/profiles.json` to break the JSON (e.g., remove the closing brace):
  ```bash
  sed -i '' -e 's/}$//' ~/.claude/bigeye-plugin/profiles.json
  ```
  Invoke `/bigeye-triage`. Expected: clean parse-error message, no silent failure, suggests `/bigeye-config init`.
- Restore the file (`/bigeye-config init` or restore from `.bak`).
- Edit the file by hand to set `default_profile` to a name that doesn't exist in `profiles`. Invoke `/bigeye-triage`. Expected: skill stops, lists available profiles, asks the user to pick one.
- Restore `default_profile` to a valid key.

- [ ] **Step 8: `/bigeye-config delete` guardrails**

- While only one profile exists, invoke `/bigeye-config delete {that_profile}`. Expected: refuses with the "only profile" error.
- Add a second profile, then delete the default. Expected: the skill asks which profile should become the new default, then writes the change.

- [ ] **Step 9: Sign-off**

If all steps pass, the implementation is verified. If any step fails, file a follow-up task describing the gap and fix before considering the feature shipped.

---

## Self-Review (completed during plan authoring)

**Spec coverage check:**
- Per-user profiles file at `~/.claude/bigeye-plugin/profiles.json` → Task 1.
- `bigeye-config` skill with show / init / add / switch / edit / delete → Task 1.
- Wizard flow (workspace, sources, tables, schemas, tags, summary) → Task 1 Step 2.
- Shared `scope.md` reference → Task 2.
- Router update → Task 3.
- Scope wired into triage / RCA / coverage / deploy / incidents → Tasks 4–8.
- Morning report agent scope → Task 9.
- RCA special case (unscoped primary lookup, scoped expansion, soft notice) → Task 5 Step 1 (narrative), Step 4 (related-issues filter), Step 5 (soft notice placement); scope.md Step I (text).
- Override flags (`--profile`, `--no-scope`, `--workspace`) → scope.md Steps B–C (Task 2); each skill's Step 0 re-references the flag parsing.
- Scope header → scope.md Step G (Task 2); each output template updated in Tasks 4–9.
- Empty-result phrasing → scope.md Step H (Task 2); triage wired in Task 4 Step 4.
- Config file schema + field rules → Task 1 Step 2 (Config File section).
- Missing / malformed config handling → scope.md Step A (Task 2).
- Invalid `default_profile` handling → scope.md Step B (Task 2).
- Out-of-scope RCA soft notice → scope.md Step I (Task 2); placement in Task 5 Step 5.
- Unresolvable `table_names` warning → scope.md Steps D + G (Task 2).
- README update → Task 10.
- Manual verification checklist → Task 11.

No gaps.

**Placeholder scan:** No TBD / TODO / "add validation" / "implement later" / bare "handle errors" entries remain. All skill content is inlined.

**Type consistency:**
- Field names used consistently: `workspace_id`, `data_source_ids`, `table_ids`, `table_names`, `schema_names`, `tags`, `default_profile`.
- Skill names consistent: `bigeye-config`, `bigeye-triage`, `bigeye-rca`, `bigeye-coverage`, `bigeye-deploy`, `bigeye-incidents`, `bigeye-morning-report`.
- Flags consistent across scope.md and each skill's Step 0: `--profile <name>`, `--no-scope`, `--workspace <id>`.
- File path consistent everywhere: `~/.claude/bigeye-plugin/profiles.json`.
- Subcommand names consistent: `show`, `init`, `add`, `switch`, `edit`, `delete`.
