# Bigeye Plugin — CLI-First Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework every Bigeye skill, the morning-report agent, and the config wizard so the CLI (`bigeye-cli`) is the primary transport and MCP becomes an optional enhancement that gracefully degrades when absent.

**Architecture:** One new shared reference (`skills/bigeye/references/cli.md`) defines the CLI invocation wrapper, the MCP-availability detection pattern, and the authoritative CLI↔MCP routing table. `bigeye-config` is extended to write both `~/.claude/bigeye-plugin/profiles.json` and the matching section in `~/.bigeye/config.ini`, drops the `tags` filter, and gains a `verify` subcommand. Every other skill is updated mechanically: read `cli.md`, detect MCP once per run, prefer CLI, fall back to MCP (or hard-fail / degrade) only for operations the CLI can't do. One new install doc (`bigeye-mcp-install.md`) teaches users how to enable MCP.

**Tech Stack:** Markdown skill files, JSON/INI config files, Bash invocations of `bigeye-cli`. No source code, no test framework. Each task's verification is either (a) confirming file content via `Read` / `Grep`, or (b) a manual scenario at the end (Task 17).

**Spec reference:** `docs/superpowers/specs/2026-04-23-bigeye-cli-migration-design.md`

---

## File Structure

**New files:**
- `skills/bigeye/references/cli.md` — CLI/MCP reference doc (see spec §3)
- `bigeye-mcp-install.md` — optional MCP install guide (see spec §6)

**Modified files:**
- `skills/bigeye/references/scope.md` — drop tags; note `-w <profile>` binding
- `skills/bigeye/references/conventions.md` — updated closing-label vocab
- `skills/bigeye/SKILL.md` — router description broadened
- `skills/bigeye-config/SKILL.md` — dual-file write, tag migration, verify subcommand, profile-name validation
- `skills/bigeye-triage/SKILL.md` — CLI for listing; MCP for clustering (degrade)
- `skills/bigeye-rca/SKILL.md` — CLI for issue details; MCP for lineage/related/resolution (degrade); `--internal-id` flag
- `skills/bigeye-coverage/SKILL.md` — MCP required for scoring; hard-fail without; CLI for history
- `skills/bigeye-deploy/SKILL.md` — bigconfig for gaps/bulk; imperative upsert for freshness/columns
- `skills/bigeye-incidents/SKILL.md` — CLI for close; MCP for create_incident; `--internal-id` flag; label remap
- `agents/bigeye-morning-report.md` — CLI primary, MCP optional with section replacement
- `hooks/hooks.json` — SessionStart message update
- `README.md` — Requirements + How it works section
- `.claude-plugin/marketplace.json` — version 0.1.0 → 0.2.0
- `pyproject.toml` — version 0.1.0 → 0.2.0

**No automated test files** — validation is manual per spec §8. Task 17 is the checklist.

**Order rationale:** Foundations first (cli.md + config wizard — Tasks 1–4) so every later task has the shared reference to point at. Triage next (Task 5) as the simplest CLI proof-of-concept. RCA/incidents share the `--internal-id` flag (Tasks 6–7). Deploy last among skills (Task 8) because the bigconfig YAML generator is the biggest piece. Coverage + morning-report close out the skill work (Tasks 9–10). Docs and version bump follow (Tasks 11–16). Manual validation last (Task 17).

---

## Task 1: Create the `cli.md` shared reference

**Files:**
- Create: `skills/bigeye/references/cli.md`

- [ ] **Step 1: Write the new reference file**

Write `skills/bigeye/references/cli.md` with exactly this content:

````markdown
# BigEye Plugin — CLI / MCP Routing

All BigEye skills MUST read this document in addition to `conventions.md` and `scope.md` before making any BigEye call. It defines:
- How to bind scope profiles to CLI workspace sections (Step A)
- How to detect MCP availability once per skill run (Step B)
- The canonical CLI invocation wrapper pattern (Step C)
- The JSON output file shapes skills consume (Step D)
- The authoritative operation routing table (Step E)
- The MCP-absence degradation warning template (Step F)
- Error-handling rules (Step G)

---

## Step A: Bind scope to CLI workspace

After `scope.md` Step B selects the active profile (say, `work-area`), every CLI invocation the skill issues MUST pass `-w work-area`. The profile name is the CLI config section name. Do this even when the profile matches the CLI's `DEFAULT` — explicit `-w` keeps transcripts self-describing.

## Step B: Detect MCP availability

Perform this exactly once per skill run, after loading scope:

1. Call `mcp__bigeye__list_data_sources` with `workspace_id: {profile's workspace_id}`.
2. On success: set `MCP_AVAILABLE=true`, discard the result.
3. On any error: set `MCP_AVAILABLE=false`, remember the error text.

Skills MUST check `MCP_AVAILABLE` before every MCP call. Do not retry MCP calls later in the same run — the result is authoritative for that run.

## Step C: CLI invocation wrapper

Use this exact pattern for any CLI call that produces output files:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> <subcommand> <subargs> -op "$TMPDIR"
# parse JSON files under $TMPDIR
```

Rules:
- Always `mktemp -d`, never a fixed path.
- Always pass `-w <profile>` (explicit even when it matches `DEFAULT`).
- Cleanup the tempdir on success. On JSON parse failure, **do not delete it** — print the path for debugging instead.
- Timeouts: 60s single-issue reads, 180s bulk dumps, 300s `bigconfig apply`.
- On non-zero exit: capture stderr and print the exact command + error to the user.

## Step D: JSON output file shapes

Each `-op <dir>` invocation produces one or more JSON files. Skills read these files, never stdout.

| Command | Files produced | Key fields |
|---|---|---|
| `issues get-issues` | one JSON per issue, named by internal ID | `id`, `displayName`, `status`, `metricConfiguration.metricType`, `dimensions[]`, `events[]`, `tableName`, `columnName`, `openedAt` |
| `metric get-info` | one JSON per metric | `id`, `metricType`, `tableName`, `columnName`, `schedule`, `recentRuns[]` |
| `catalog get-metric-info` | per-metric JSONs under warehouse/schema/table tree | same as `metric get-info` |
| `catalog get-table-info` | per-table JSONs | `id`, `schemaName`, `tableName`, `columns[]`, `metricCount` |
| `bigconfig plan` | report file + fixme files | report summary for confirmation gate |
| `bigconfig apply` | apply report | success / failure counts; created metric IDs |

Implementation note: exact filenames are workspace-dependent; skills that need specific files should enumerate via `ls "$TMPDIR"` and parse the union of JSON files.

## Step E: Operation routing table

Authoritative mapping. "Required" means MCP is needed when CLI has no equivalent — if MCP is absent, follow Step F and degrade per each skill's documented rules.

| Operation | CLI | MCP |
|---|---|---|
| List / dump issues | `issues get-issues` | — |
| Get single issue by internal ID | `issues get-issues -iid` | — |
| Resolve display-name → internal ID | — | `search_issues` (required) |
| Acknowledge / close issue | `issues update-issue` | — |
| List related issues (clustering) | — | `list_related_issues` (required) |
| Lineage trace (RCA upstream) | — | `get_issue_lineage_trace` (required) |
| Resolution steps (AI) | — | `get_resolution_steps` (required) |
| Table dimension coverage | — | `get_table_dimension_coverage` (required) |
| Column dimension coverage | — | `get_column_dimension_coverage` (required) |
| Dimension taxonomy | — | `list_dimensions` (required) |
| Table enumeration | `catalog get-table-info` | — |
| Data-source listing | — | `list_data_sources` (required) |
| Deploy — bulk / gaps | `bigconfig plan` + `apply` | — |
| Deploy — freshness / explicit columns | `metric upsert -t SIMPLE` | — |
| Tag CRUD (`deployed-by-plugin`) | — | `list_tags` / `create_tag` / `tag_entity` (required) |
| Create / merge incident | — | `create_incident` (required) |

## Step F: MCP-absence warning template

When a skill would call MCP but `MCP_AVAILABLE=false`, print exactly this block before continuing (or skipping, per the skill's rules):

```
Note: MCP server unavailable — {feature_name} skipped.
  Reason: {error captured in Step B}
  To enable, see bigeye-mcp-install.md.
  {CLI-only workaround if any}
```

No emoji. Populate `{feature_name}` from the per-skill table. `{CLI-only workaround if any}` is the skill's recommended next action (or omitted).

## Step G: Error-handling rules

- Clear CLI auth error (stderr contains `401` or `Config file not found`): stop the skill and print *"BigEye CLI auth not configured. Run `/bigeye-config init` or see bigeye-cli-install.md."*
- Scope error (bad warehouse ID — CLI returns `404` or `No such warehouse`): print the command that ran + stderr; suggest `/bigeye-config show` to verify values.
- JSON parse error on `-op` output: print the tempdir path (do not delete), ask the user to paste the file contents for diagnosis.
- Partial write success: report success count + failed items; skip chaining suggestions until fixed.

## Step H: Per-skill routing summary

| Skill | Uses CLI for | Uses MCP for | Behavior on MCP absence |
|---|---|---|---|
| `bigeye-triage` | issue listing | cluster detection | cluster section replaced with note; rest renders |
| `bigeye-rca` | issue details by ID | display-name lookup, lineage, related, resolution | display-name hard-fails unless `--internal-id`; lineage/related/resolution skipped with notes |
| `bigeye-coverage` | issue history (non-critical) | dimension coverage scoring | hard-fail with pointer |
| `bigeye-deploy` (gaps/bulk) | bigconfig plan/apply | coverage discovery, tag ops | hard-fail (coverage unavailable) |
| `bigeye-deploy` (freshness) | metric upsert | tag ops | works; tagging skipped |
| `bigeye-deploy` (columns) | metric upsert | per-column dimension inference, tag ops | works only with explicit `--metric-type` flag; tagging skipped |
| `bigeye-incidents` (close) | update-issue | display-name lookup | close works with `--internal-id`; otherwise hard-fails with pointer |
| `bigeye-incidents` (create/auto) | issue listing | create_incident, related_issues, display-name lookup | create hard-fails |
| `bigeye-morning-report` | issue listing | clustering, coverage scoring | cluster/coverage sections replaced with notes |
````

- [ ] **Step 2: Verify file content**

Run:
```bash
head -20 /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/cli.md
wc -l /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/cli.md
```

Expected: first line is `# BigEye Plugin — CLI / MCP Routing`; total lines ~125.

- [ ] **Step 3: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye/references/cli.md
```

---

## Task 2: Update `scope.md` — drop tags, pass `-w <profile>`

**Files:**
- Modify: `skills/bigeye/references/scope.md`

- [ ] **Step 1: Remove the Tags wizard step and field references**

In `skills/bigeye/references/scope.md`:

1. In the Schema rules section, remove `tags` from the MCP parameter map table (Step E).
2. Add a new Step F.1 (between F and G) titled "CLI parameter binding" that says:
   > When invoking the CLI, pass `-w <profile_name>` so the CLI resolves its workspace section. See `cli.md` Step A.
3. In Step A (Locate the Config File), after the existing JSON-parse error block, add:
   > If the loaded profile contains a non-empty `tags` field, strip it from the working copy in memory. Print once per session: *"Note: `tags` filter removed in this plugin release — stripping from profile `<name>` on read. Next `/bigeye-config edit <name>` will rewrite without the field."* Do not modify the file on disk until the wizard rewrites it.

- [ ] **Step 2: Remove the Tags row from the MCP parameter table**

Apply this exact change to Step E:

Before:
```
| `table_ids` (including resolved table_names) | `table_ids` |
| `schema_names` | `schema_names` |
| `tags` | `tags` |
```

After:
```
| `table_ids` (including resolved table_names) | `table_ids` |
| `schema_names` | `schema_names` |
```

- [ ] **Step 3: Update the Scope header format**

In Step G (Print the Scope Header), replace the template line:
```
Scope: profile={name} · workspace={id} · sources={count} · tables={count} · schemas={count} · tags={count}
```
with:
```
Scope: profile={name} · workspace={id} · sources={count} · tables={count} · schemas={count}
```

Remove any mention of tags in the "unresolved table names" example.

- [ ] **Step 4: Verify**

Run:
```bash
grep -n tags /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/scope.md
```

Expected: remaining `tags` references only in the tag-migration notice (Step A addendum from Step 1).

- [ ] **Step 5: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye/references/scope.md
```

---

## Task 3: Update `conventions.md` — closing-label vocab

**Files:**
- Modify: `skills/bigeye/references/conventions.md`

- [ ] **Step 1: Replace the Closing Labels section**

Find the existing section:
```
## Closing Labels

When closing issues, use one of:
- `METRIC_RUN_LABEL_TRUE_NEGATIVE`: Real issue, now resolved
- `METRIC_RUN_LABEL_FALSE_POSITIVE`: Not a real issue (noisy monitor)
```

Replace with:
```
## Closing Labels

When closing issues via the CLI (`bigeye issues update-issue -cl <label>`), use one of:
- `TRUE_POSITIVE`: Real issue, now resolved
- `FALSE_POSITIVE`: Not a real issue (noisy monitor)
- `EXPECTED`: Known exception — expected behavior, not an actual issue

Skills that accept a user-facing shorthand flag (`--label`) MUST remap it to the CLI label as follows:

| Shorthand | CLI label |
|---|---|
| `true-negative` | `TRUE_POSITIVE` |
| `false-positive` | `FALSE_POSITIVE` |
| `expected` | `EXPECTED` |

(The `true-negative` → `TRUE_POSITIVE` mapping is intentional: what the plugin previously called a "true negative" is what the CLI calls a "true positive" — the flag name is kept for backward compatibility with prior plugin versions.)
```

- [ ] **Step 2: Verify**

Run:
```bash
grep -n METRIC_RUN_LABEL /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/conventions.md
```

Expected: no matches.

- [ ] **Step 3: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye/references/conventions.md
```

---

## Task 4: Rewrite `bigeye-config` skill — dual-file writes, tag migration, verify, name validation

**Files:**
- Modify: `skills/bigeye-config/SKILL.md`

- [ ] **Step 1: Replace the skill with the new version**

Overwrite `skills/bigeye-config/SKILL.md` with exactly this content:

````markdown
---
name: bigeye-config
description: Use when the user wants to configure the BigEye plugin's scope (workspace + filters), run the first-run wizard, manage named profiles, or verify CLI/MCP setup. Also auto-invoked by other BigEye skills when the config file is missing.
user-invocable: true
---

# BigEye Configuration

Owns the per-user profiles file at `~/.claude/bigeye-plugin/profiles.json` AND the matching workspace sections of `~/.bigeye/config.ini`. This is the **only** skill that writes to either file.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for shared output formatting and `skills/bigeye/references/cli.md` for CLI invocation rules.

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
| `verify` / `verify <name>` | Run a four-point health check (CLI install, CLI workspace, CLI auth, MCP reachability) and print a status table |

## Config Files

**`~/.claude/bigeye-plugin/profiles.json`** — plugin-owned; contains profile definitions + default pointer.

**Schema** (note: `tags` field removed in this version):

```json
{
  "default_profile": "work-area",
  "profiles": {
    "work-area": {
      "workspace_id": 42,
      "data_source_ids": [17],
      "table_ids": [],
      "table_names": ["orders_main"],
      "schema_names": []
    }
  }
}
```

**`~/.bigeye/config.ini`** — plugin writes the section matching the profile name:

```ini
[work-area]
workspace_id = 42
```

**`~/.bigeye/credentials`** — user-owned, never touched by the plugin.

**Field rules:**
- `default_profile` must reference a key in `profiles`.
- Each profile requires `workspace_id`. All other fields are optional arrays.
- Missing filter fields default to empty arrays when written.
- `tags` is removed — see migration below.

## Profile-Name Validation

Profile names MUST match `^[a-zA-Z0-9_-]+$`. Reject anything else at the wizard's first step. The name `DEFAULT` is rejected unless the user explicitly confirms they want to overwrite the CLI's default section.

## Tag Migration

On every read of `profiles.json`:
1. If any profile contains a non-empty `tags` field, strip it in-memory before use.
2. Print once per session:
   ```
   Note: `tags` filter removed in this plugin release.
   Stripping from profile `<name>` on read. Run `/bigeye-config edit <name>` to rewrite cleanly.
   ```
3. Do not modify the on-disk file until the wizard writes it next.

## Procedure

### Subcommand: `show` (or no argument)

1. Read `~/.claude/bigeye-plugin/profiles.json`. If missing:
   ```
   No BigEye profiles configured yet.
   Run `/bigeye-config init` to set one up.
   ```
   Stop.
2. Parse the JSON; apply tag migration.
3. Print:
   ```
   ## BigEye Profiles

   Active (default): **{default_profile}**

   | Profile | Workspace | Sources | Tables | Schemas |
   |---------|-----------|---------|--------|---------|
   | {name} | {workspace_id} | {count} | {count} | {count} |
   ```

### Subcommand: `init`

1. Read `~/.claude/bigeye-plugin/profiles.json`. If it exists, ask:
   ```
   A config file already exists. What would you like to do?
   1. Overwrite with a new default profile
   2. Add a new profile alongside the existing ones
   3. Cancel
   ```
2. If it does not exist, ask: *"What would you like to name this profile? (default: `work-area`)"*. Validate per Profile-Name Validation rules.
3. Run the **Wizard Flow** below.
4. Ensure the directory exists:
   ```bash
   mkdir -p ~/.claude/bigeye-plugin
   mkdir -p ~/.bigeye
   ```
5. Write `~/.claude/bigeye-plugin/profiles.json` with the final content.
6. Add/replace the `[<profile>]` section in `~/.bigeye/config.ini` with `workspace_id = <id>` (leave all other sections untouched). If `~/.bigeye/config.ini` doesn't exist, create it with only the new section (no implicit `[DEFAULT]`).
7. Verify CLI binding:
   ```bash
   bigeye -w <profile> configure list
   ```
   On non-zero exit, print the CLI error and a note:
   *"CLI workspace configured, but `bigeye configure list` failed. You likely need to set up `~/.bigeye/credentials` via `bigeye configure` or by following `bigeye-cli-install.md`."*
8. Print:
   ```
   Wrote profile `{name}` to:
     ~/.claude/bigeye-plugin/profiles.json (set as default)
     ~/.bigeye/config.ini (section [{name}], workspace_id={id})

   Try `/bigeye-config verify` to confirm setup, then `/bigeye-triage` for scoped issues.
   ```

### Subcommand: `add <name>`

1. Validate `<name>` per Profile-Name Validation rules.
2. Read existing `profiles.json`. If missing, tell the user to run `/bigeye-config init` first.
3. If `[<name>]` already exists in `~/.bigeye/config.ini`, print current contents and ask:
   *"A CLI section `[<name>]` already exists with workspace_id=<X>. Overwrite with the new profile's workspace_id? (y/n/pick-different-name)"*.
4. Run the Wizard Flow.
5. Merge new profile into `profiles`. Do not change `default_profile`.
6. Add/replace `[<name>]` in `~/.bigeye/config.ini`.
7. Print confirmation.

### Subcommand: `switch <name>`

1. Read `profiles.json`. If missing, tell the user to run `/bigeye-config init`.
2. If `<name>` not in `profiles`, print available and stop.
3. Update `default_profile` to `<name>`; write file.
4. Print: `Switched default profile to \`{name}\`.`

### Subcommand: `edit <name>`

1. Read file. If missing or `<name>` not in `profiles`, error.
2. Show current values. Apply tag migration.
3. Run Wizard Flow with current values pre-filled (let user press enter to keep each).
4. Replace the profile. Do not change `default_profile`.
5. Write `profiles.json`. Update `[<name>]` in `~/.bigeye/config.ini` with the new `workspace_id`.
6. Print confirmation.

### Subcommand: `delete <name>`

1. Read file. If missing or `<name>` not in `profiles`, error.
2. If `<name>` is the `default_profile`:
   - If only one profile exists: refuse. Print the standard error and stop.
   - Otherwise: ask which profile to promote as the new default.
3. Ask confirmation: *"Also remove `[<name>]` from `~/.bigeye/config.ini`? (y/n) — Other tools on this machine may be using this section."*
4. Remove profile from `profiles.json`. If user confirmed, remove the section from `config.ini`.
5. Write file(s). Print confirmation listing exactly what was removed.

### Subcommand: `verify` / `verify <name>`

Resolve the profile name (argument or active default). Print:

```
BigEye Plugin — Setup Status

[{a}] CLI installed            {bigeye --version output or "not on PATH"}
[{b}] CLI workspace configured [{profile}] → workspace_id={id} (~/.bigeye/config.ini)
[{c}] CLI auth                 {~/.bigeye/credentials status}
[{d}] MCP server reachable     {MCP probe result}
                              {when reachable: feature list enabled by MCP}

Overall: {ready / partially degraded / setup required}
```

Status markers use plain ASCII: `[✓]` (good), `[!]` (warn), `[✗]` (fail), `[~]` (info). `[✓]` stays literal despite being a Unicode character — it's a well-established ASCII-ish status marker and not emoji.

Check steps:
- **a**: run `which bigeye`. If non-zero, mark `[✗]` and suggest `bigeye-cli-install.md`.
- **b**: read the resolved profile's `workspace_id`, confirm `[<profile>]` exists in `~/.bigeye/config.ini` with that value. Mismatch → `[!]`.
- **c**: `test -r ~/.bigeye/credentials`. Absent → `[!]`, point at `bigeye configure`.
- **d**: call `mcp__bigeye__list_data_sources` with `workspace_id`. On success, list the features MCP unlocks. On failure, mark `[!]` and point at `bigeye-mcp-install.md`.

Always exit printing the table. Never fail the session.

## Wizard Flow

Ask one question at a time. Show the running summary after each answer.

1. **Workspace ID.** Ask: *"What's your BigEye workspace_id? (integer)"*. Validate integer. If `mcp__bigeye__list_data_sources` is available, call with `workspace_id: {answer}` to confirm reachability; warn but don't block on error.
2. **Data sources.** Ask: *"Filter by data source? (y/n)"*.
   - If yes and MCP is available: call `mcp__bigeye__list_data_sources`, show as numbered list, let user pick indices. Store resolved integer IDs in `data_source_ids`.
   - If yes and MCP is absent: print *"MCP not available — enter warehouse IDs one per line (blank to finish). Find these in the BigEye UI under Settings → Sources."* Store the integers in `data_source_ids`.
3. **Tables.** Ask: *"Filter by specific tables? (y/n)"*. If yes, ask for one name per line. Resolve via whichever MCP tool is available (`mcp__bigeye-knowledgebase__search_metadata` or `mcp__bigeye__list_tables`). Store names in `table_names` and resolved IDs in `table_ids`. Warn on unresolved names; don't block.
4. **Schemas.** Ask: *"Filter by schema? (y/n)"*. Store in `schema_names`.
5. **Summary and confirmation.** Show:
   ```
   Profile summary:
     workspace_id: {...}
     data_source_ids: [...]
     table_names: [...]
     table_ids: [...]
     schema_names: [...]

   Will write:
     ~/.claude/bigeye-plugin/profiles.json (profile '{name}')
     ~/.bigeye/config.ini (section [{name}], workspace_id={id})

   Save this profile? (y/n)
   ```
   On `n`, restart. On `y`, proceed to the caller's write step.

Tags are NOT asked — the field is removed.

## Notes

- Pretty-print JSON with 2-space indent.
- Never write comments in JSON.
- Handle `FileNotFoundError` as "no config yet."
- On JSON parse error, print the error and suggest `/bigeye-config init`.
- When editing `~/.bigeye/config.ini`, parse-preserve-rewrite: never re-order, never remove sections the plugin doesn't own, never add comments.
````

- [ ] **Step 2: Verify key sections exist**

Run:
```bash
grep -nE '^###? Subcommand: (verify|init|add|edit|delete|switch|show)' /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-config/SKILL.md
```

Expected: seven subcommand headers, including `verify`.

- [ ] **Step 3: Confirm tags field is absent from the new schema**

Run:
```bash
grep -nE '"tags"|tag_ids|tags: \[\]' /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-config/SKILL.md
```

Expected: no matches (the only `tags` mentions should be in the migration section — verify those references are narrative only).

- [ ] **Step 4: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye-config/SKILL.md
```

---

## Task 5: Update `bigeye-triage` — CLI for listing, degrade on clustering

**Files:**
- Modify: `skills/bigeye-triage/SKILL.md`

- [ ] **Step 1: Update the "Before doing anything else" line**

Replace:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for severity classification rules and output formatting, and `skills/bigeye/references/scope.md` for how to load and apply the active scope profile.
```
with:
```
**Before doing anything else**, read `skills/bigeye/references/conventions.md` for severity classification rules and output formatting, `skills/bigeye/references/scope.md` for how to load and apply the active scope profile, and `skills/bigeye/references/cli.md` for CLI invocation rules and MCP-availability detection.
```

- [ ] **Step 2: Update Step 0 to include MCP detection**

Replace the current Step 0 body:
```
Follow `skills/bigeye/references/scope.md` (Steps A–E) to load the active profile and build the parameter map. Parse and honor `--profile <name>`, `--no-scope`, and `--workspace <id>` flags from `$ARGUMENTS` before parsing the skill's own arguments.
```
with:
```
Follow `skills/bigeye/references/scope.md` (Steps A–E) to load the active profile. Parse and honor `--profile <name>`, `--no-scope`, and `--workspace <id>` flags from `$ARGUMENTS` before parsing the skill's own arguments. Then follow `cli.md` Step B to detect MCP availability (sets `MCP_AVAILABLE`).
```

- [ ] **Step 3: Replace Step 1 (Fetch Active Issues) to use CLI**

Replace the entire Step 1 body with:
```
Use CLI per `cli.md` Step C:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> issues get-issues \
  {if data_source_ids non-empty: for each id, append `-wid <id>`} \
  {if schema_names non-empty: for each name, append `-sn <name>`} \
  -op "$TMPDIR"
```

Parse each JSON file in `$TMPDIR`. Filter in-memory:
- Keep only issues whose `status` is `ISSUE_STATUS_NEW` or `ISSUE_STATUS_ACKNOWLEDGED`.
- If the `new` argument was supplied, keep only `ISSUE_STATUS_NEW`.
- If the `24h` argument was supplied, keep only issues with `openedAt` within the last 24 hours.
- Cap at `max_issues` (50 by default, or the user's override).

If the filtered list is empty, print the empty-result message per `scope.md` Step H and stop.

Note: the CLI has no `--tag` filter; scope tags are no longer supported.
```

- [ ] **Step 4: Update Step 3 (Detect Issue Clusters) for MCP fallback**

Replace Step 3 body with:
```
If `MCP_AVAILABLE=true`:
  For each Critical and Warning issue, call `mcp__bigeye__list_related_issues` with `starting_issue_id: <issue_id>`. Count related issues per issue. Flag any with 2+ related as a cluster.

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=cluster detection`. Set `cluster_count=null` for the output. Do not call MCP.
```

- [ ] **Step 5: Update Step 4 (Format Output) for degradation**

After the existing Summary section template, add this conditional line:
```
If `cluster_count` is null (MCP absent), replace the `{cluster_count} issue clusters detected (potential shared root cause)` line with: `Cluster detection disabled — MCP not configured (see bigeye-mcp-install.md).`
```

- [ ] **Step 6: Verify**

Run:
```bash
grep -n 'bigeye -w' /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-triage/SKILL.md
grep -n MCP_AVAILABLE /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-triage/SKILL.md
```

Expected: at least one `bigeye -w` invocation, at least two `MCP_AVAILABLE` checks.

- [ ] **Step 7: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye-triage/SKILL.md
```

---

## Task 6: Update `bigeye-rca` — CLI for details, MCP-degrade, `--internal-id` flag

**Files:**
- Modify: `skills/bigeye-rca/SKILL.md`

- [ ] **Step 1: Update the "Before doing anything else" line**

Append `, and `skills/bigeye/references/cli.md` for CLI invocation rules and MCP-availability detection` to the existing sentence (same pattern as Task 5 Step 1).

- [ ] **Step 2: Add `--internal-id` to the Arguments section**

Add a bullet to the Arguments section:
```
- `--internal-id`: treat the numeric argument as an internal ID instead of a display name. Skips the MCP display-name lookup. Required when MCP is unavailable.
```

- [ ] **Step 3: Update Step 0 to include MCP detection**

Same edit as Task 5 Step 2 (add the `cli.md Step B` sentence).

- [ ] **Step 4: Replace Step 1 (Resolve the Issue)**

Replace the entire Step 1 body with:
```
### Step 1: Resolve the Issue

Parse the argument:
- If `--internal-id` was provided, treat the number as an internal ID directly; set `internal_id={number}`. Skip the MCP lookup.
- If no argument was provided, run the fallback described below (auto-select top critical).
- Otherwise the number is a display name; must be resolved via MCP.

**Display-name → internal-ID lookup (MCP required):**

If `MCP_AVAILABLE=true`:
  Call `mcp__bigeye__search_issues` with `name_query: "{number}"`. If no match, tell the user and stop. If multiple, list and ask which. Extract `id` (internal ID).

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=display-name lookup` and `{CLI-only workaround}=Re-run with --internal-id <internal-id> (find the internal ID in the Bigeye UI URL: app.bigeye.com/issue/<internal-id>)`. Stop the skill — there's nothing useful to show without an internal ID.

**If no argument was provided (auto-select):**

Use the CLI per `cli.md` Step C to fetch the 5 most recent NEW issues (equivalent of the old list_issues call):

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> issues get-issues -op "$TMPDIR"
```

Read the JSON files, filter to `ISSUE_STATUS_NEW`, apply severity per `conventions.md`, pick the top Critical (or top Warning if no Critical). Use that issue's `id` as `internal_id`. Tell the user which issue was auto-selected and why.
```

- [ ] **Step 5: Replace Step 2 (Get Full Issue Details) to use CLI**

Replace Step 2 body with:
```
Use CLI per `cli.md` Step C:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> issues get-issues -iid <internal_id> -op "$TMPDIR"
```

Read the single JSON file. Extract and note:
- Metric type (`metricConfiguration.metricType`)
- Table (`tableName`) and column (`columnName`)
- When started (`openedAt` — first event timestamp in `events[]`)
- Current status (`status`)
- Event history (`events[]`)
```

- [ ] **Step 6: Update Steps 3, 4, 5 for MCP degradation**

For each of Step 3 (Trace Lineage), Step 4 (Get Related Issues), Step 5 (Get Resolution Steps), prepend:

```
If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=<lineage trace|related issues|resolution steps>`. Skip this step. Proceed to the next.

If `MCP_AVAILABLE=true`:
  <existing body unchanged>
```

(Use the exact existing body for each step; only prepend the conditional.)

- [ ] **Step 7: Update Step 6 (Format Output) to prepend degraded banner**

Add this instruction at the top of Step 6:
```
If any MCP step was skipped, insert this line immediately after the Scope: header, before the main `## Root Cause Analysis — Issue #{...}` heading:

```
Reduced RCA — MCP unavailable. Lineage, related issues, and/or resolution steps omitted. See bigeye-mcp-install.md.
```

For any MCP section that was skipped (Lineage Trace, Related Issues, Resolution Steps), replace its body with the single line: `(skipped — MCP unavailable)`.
```

- [ ] **Step 8: Verify**

Run:
```bash
grep -n 'bigeye -w\|MCP_AVAILABLE\|--internal-id' /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-rca/SKILL.md
```

Expected: at least one `bigeye -w`, several `MCP_AVAILABLE`, at least one `--internal-id`.

- [ ] **Step 9: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye-rca/SKILL.md
```

---

## Task 7: Update `bigeye-incidents` — CLI for close, MCP for create, `--internal-id`, label remap

**Files:**
- Modify: `skills/bigeye-incidents/SKILL.md`

- [ ] **Step 1: Update the "Before doing anything else" line**

Add the `cli.md` reference as in Task 5 Step 1.

- [ ] **Step 2: Add `--internal-id` to Arguments**

Add bullet:
```
- `--internal-id`: treat all numeric arguments in this invocation as internal IDs instead of display names. Required when MCP is unavailable (display-name lookup needs MCP).
```

- [ ] **Step 3: Update Step 0 for MCP detection**

Add the `cli.md` Step B sentence (pattern as Task 5).

- [ ] **Step 4: Wrap `search_issues` calls with MCP gating**

In every mode that resolves display names (Merge Specific Issues Step 1, Add to Existing, Close mode), replace the direct `mcp__bigeye__search_issues` call with:

```
If `--internal-id` was passed, treat the given number(s) as internal IDs directly.

Otherwise, if `MCP_AVAILABLE=true`:
  Call `mcp__bigeye__search_issues` with `name_query: "{display_name}"` to resolve each display name to an internal ID.

Otherwise (MCP absent and no `--internal-id`):
  Print the `cli.md` Step F warning with `{feature_name}=display-name lookup` and `{CLI-only workaround}=Re-run with --internal-id`. Stop the skill.
```

- [ ] **Step 5: Wrap `list_related_issues` with MCP gating**

In Merge Specific Issues Step 2 (Validate relationship), prepend:
```
If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=relationship validation` and continue without validation. Skip to Step 3.

If `MCP_AVAILABLE=true`:
  <existing body>
```

Same pattern for Auto-Detect Step 2 (Build relationship graph) — if MCP absent, skip auto-detect entirely and print the warning with `{feature_name}=cluster auto-detection`; print *"Cannot auto-detect clusters without MCP — see bigeye-mcp-install.md."* and stop.

- [ ] **Step 6: Hard-fail on create_incident when MCP absent**

In Merge Specific Issues Step 5 (Create incident) and Add to Existing Step 2, prepend:
```
If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=incident creation`. Stop — no CLI equivalent exists.
```

- [ ] **Step 7: Replace Close mode to use CLI**

Replace the entire Close mode body with:
```
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
```

- [ ] **Step 8: Update Auto-Detect Step 1 (Fetch open issues) to use CLI**

Replace the `mcp__bigeye__list_issues` call with the CLI invocation:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> issues get-issues \
  {if data_source_ids non-empty: for each id, append `-wid <id>`} \
  {if schema_names non-empty: for each name, append `-sn <name>`} \
  -op "$TMPDIR"
```

Read each JSON file in `$TMPDIR`; filter in-memory to `status in {ISSUE_STATUS_NEW, ISSUE_STATUS_ACKNOWLEDGED}`; cap at 50 issues.

- [ ] **Step 9: Verify**

Run:
```bash
grep -n 'bigeye -w\|MCP_AVAILABLE\|--internal-id\|TRUE_POSITIVE\|FALSE_POSITIVE\|EXPECTED' /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-incidents/SKILL.md
```

Expected: CLI invocations, MCP gates, `--internal-id`, all three CLI label values.

- [ ] **Step 10: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye-incidents/SKILL.md
```

---

## Task 8: Update `bigeye-deploy` — bigconfig for gaps/bulk, imperative for freshness/columns

**Files:**
- Modify: `skills/bigeye-deploy/SKILL.md`

- [ ] **Step 1: Update the "Before doing anything else" line + arguments**

Add `cli.md` to the readlist (same pattern as Task 5).

Add a new bullet to Arguments:
```
- `--metric-type <TYPE>`: required for `columns <list>` when MCP is unavailable. Applies the same metric type to all named columns. Valid types: `PERCENT_NULL`, `COUNT_DISTINCT`, `COUNT_ROWS`, `FRESHNESS`, etc. (see Bigeye docs).
```

- [ ] **Step 2: Update Step 0**

Add `cli.md` Step B MCP-detection sentence.

- [ ] **Step 3: Replace Step 1 (Build Deployment Plan)**

Replace the entire Step 1 body with:
```
### Step 1: Build Deployment Plan

**For `gaps` / `bulk <dimension>` arguments** (bigconfig path):

1. If `MCP_AVAILABLE=false`:
   Print the `cli.md` Step F warning with `{feature_name}=coverage-driven deploy planning`. Stop — gaps/bulk hard-fail without coverage scoring.
2. Call `mcp__bigeye__get_table_dimension_coverage` per in-scope table to enumerate gaps.
3. Filter by `--priority high` (HIGH only) or `--priority medium` (HIGH + MEDIUM) if given.
4. For `bulk <dimension>`, filter the gap list to only that dimension.
5. Build a bigconfig YAML at `$TMPDIR/bigconfig.yaml` describing the desired metrics. Template (fill placeholders):
   ```yaml
   type: BIGCONFIG_FILE
   tag_deployments:
     - collection:
         name: plugin-deployed
       deployments:
         - fq_table_name: <data_source>.<schema>.<table>
           columns:
             - column_name: <column>
               metrics:
                 - saved_metric_id: <auto-named-id>
                   metric_type:
                     predefined_metric:
                       metric_name: <METRIC_TYPE>
                   lookback:
                     lookback_window: { interval_type: DAYS, interval_value: 7 }
                     lookback_type: DATA_TIME
   ```
   (If the exact Bigconfig schema differs when implementing, verify against `bigeye bigconfig export -op /tmp/sample` on a real workspace and correct the template.)

**For `columns <list>` argument** (imperative path):

1. If `MCP_AVAILABLE=true` and `--metric-type` was not passed:
   Call `mcp__bigeye__get_column_dimension_coverage` with `column_names` to infer a metric type per column per dimension.
2. If `MCP_AVAILABLE=false` and `--metric-type` was not passed:
   Print the `cli.md` Step F warning with `{feature_name}=per-column dimension inference` and `{CLI-only workaround}=Re-run with --metric-type <TYPE> to apply a single type to all columns`. Stop.
3. If `--metric-type` was passed: skip inference, use that type for every column.
4. Build one `SimpleUpsertMetricRequest` YAML file per column at `$TMPDIR/<column>.yaml`.

**For `freshness` argument** (imperative path, no MCP):

Build one `SimpleUpsertMetricRequest` YAML at `$TMPDIR/freshness.yaml` targeting a table-level `FRESHNESS` metric.

Template for `SimpleUpsertMetricRequest` (verify exact shape when implementing):
```yaml
schema_name: <schema>
table_name: <table>
column_name: <column or empty for table-level>
metric_type: <METRIC_TYPE>
lookback:
  lookback_window: { interval_type: DAYS, interval_value: 7 }
  lookback_type: DATA_TIME
```
```

- [ ] **Step 4: Replace Step 2 (Present Deployment Plan) to show CLI command**

After the existing plan table, add a line showing the exact CLI invocation:
```
For bigconfig path: `bigeye -w <profile> bigconfig plan -ip $TMPDIR -op $TMPDIR/plan/` (then `apply -auto_approve` on confirm).
For imperative path: `bigeye -w <profile> metric upsert -f <file> -t SIMPLE` per file.
```

- [ ] **Step 5: Update Step 3 (Ensure Tracking Tag Exists) for MCP gating**

Prepend:
```
If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=monitor tagging` and `{CLI-only workaround}=Monitors will be created but not tagged — `deployed-by-plugin` tracking unavailable without MCP`. Set `SKIP_TAGGING=true`. Skip to Step 4.

If `MCP_AVAILABLE=true`:
  <existing body>
```

- [ ] **Step 6: Replace Step 4 (Create Monitors) with the bigconfig / upsert branches**

Replace Step 4 entirely with:
```
### Step 4: Create Monitors

**Bigconfig path** (for `gaps` / `bulk`):

1. Run plan:
   ```bash
   bigeye -w <profile> bigconfig plan -ip "$TMPDIR" -op "$TMPDIR/plan"
   ```
2. Read the plan report; summarize to the user: *"Plan: N monitors to create, M to update, 0 errors."*
3. Ask re-confirmation: *"Apply now? (y/n)"*. On `n`, stop.
4. Run apply:
   ```bash
   bigeye -w <profile> bigconfig apply -ip "$TMPDIR" -auto_approve
   ```
5. Read the apply report. Extract created metric IDs (for tagging in Step 5).

**Imperative path** (for `freshness` / `columns`):

For each YAML file in `$TMPDIR`:
```bash
bigeye -w <profile> metric upsert -f <file_path> -t SIMPLE
```
Track successes and failures. Parse each command's output for the created metric ID.
```

- [ ] **Step 7: Update Step 5 (Tag Created Monitors) for SKIP_TAGGING**

Prepend:
```
If `SKIP_TAGGING=true` (from Step 3):
  Skip this step entirely.
```

- [ ] **Step 8: Update Step 6 (Report Results)**

Add a conditional line:
```
If `SKIP_TAGGING=true`, append to the output:
`Note: monitors were NOT tagged (MCP unavailable). To backfill tags later, run `/bigeye-config verify` and then deploy again once MCP is configured.`
```

- [ ] **Step 9: Verify**

Run:
```bash
grep -n 'bigeye -w\|MCP_AVAILABLE\|--metric-type\|bigconfig\|SKIP_TAGGING' /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-deploy/SKILL.md
```

Expected: CLI invocations for both `bigconfig` and `metric upsert`; MCP gates; `--metric-type`; `SKIP_TAGGING` flag.

- [ ] **Step 10: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye-deploy/SKILL.md
```

---

## Task 9: Update `bigeye-coverage` — hard-fail without MCP, CLI for history

**Files:**
- Modify: `skills/bigeye-coverage/SKILL.md`

- [ ] **Step 1: Update the "Before doing anything else" line**

Add `cli.md` (Task 5 pattern).

- [ ] **Step 2: Update Step 0**

Add `cli.md` Step B MCP-detection sentence.

- [ ] **Step 3: Prepend Steps 1–3 with hard-fail gate**

At the top of Step 1 (Get Table Dimension Coverage), prepend:
```
If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=dimension coverage scoring` and `{CLI-only workaround}=Coverage scoring has no CLI equivalent. Enable MCP via bigeye-mcp-install.md. You can still see which columns have monitors via `bigeye -w <profile> catalog get-metric-info -tid <id> -op <tmp>`, but dimension-level coverage requires MCP.` Stop the skill.
```

Apply the same gate at the top of Step 2 (Get Dimension Taxonomy) and Step 3 (Get Column-Level Detail) — redundant but explicit for safety.

- [ ] **Step 4: Replace Step 4 (Prioritize Gaps) history fetch to use CLI**

Replace the `mcp__bigeye__list_table_issues` call with:
```
Fetch past issues via CLI:
```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> issues get-issues \
  {per in-scope warehouse_id: -wid <id>} \
  {per in-scope schema: -sn <name>} \
  -op "$TMPDIR"
```

Read JSON files; filter to issues whose `tableName` matches the current table; keep `NEW`, `ACKNOWLEDGED`, and `CLOSED` (for the 30-day history).
```

- [ ] **Step 5: Verify**

Run:
```bash
grep -n 'bigeye -w\|MCP_AVAILABLE' /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-coverage/SKILL.md
```

Expected: at least one CLI invocation; MCP gate present.

- [ ] **Step 6: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye-coverage/SKILL.md
```

---

## Task 10: Update `bigeye-morning-report` agent

**Files:**
- Modify: `agents/bigeye-morning-report.md`

- [ ] **Step 1: Add `cli.md` to the readlist**

Replace the sentence `Before starting, read skills/bigeye/references/conventions.md ... and skills/bigeye/references/scope.md ...` to also include `skills/bigeye/references/cli.md`.

- [ ] **Step 2: Update Step 0 to include MCP detection**

Add the MCP-detection sentence per `cli.md` Step B.

- [ ] **Step 3: Replace Step 1 (Triage — Current Issue State) to use CLI**

Replace the `mcp__bigeye__list_issues` call with:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> issues get-issues \
  {if data_source_ids non-empty: for each id, append `-wid <id>`} \
  {if schema_names non-empty: for each name, append `-sn <name>`} \
  -op "$TMPDIR"
```

Read each JSON file in `$TMPDIR`; filter in-memory to `status in {ISSUE_STATUS_NEW, ISSUE_STATUS_ACKNOWLEDGED}`; cap at 50. Classify severity per `conventions.md`.

- [ ] **Step 4: Update Step 2 (Cluster Detection) for MCP gating**

Prepend:
```
If `MCP_AVAILABLE=false`:
  Skip cluster detection. Set `cluster_count=null`. Do not print a warning to stdout (the scheduled run is unattended; the report body carries the note).

If `MCP_AVAILABLE=true`:
  <existing body>
```

- [ ] **Step 5: Update Step 3 (Coverage Check) for MCP gating**

Prepend:
```
If `MCP_AVAILABLE=false`:
  Skip coverage scoring. Set `coverage_percent="skipped (MCP unavailable)"`. Do not call MCP.

If `MCP_AVAILABLE=true`:
  <existing body>
```

- [ ] **Step 6: Update Step 4 (Produce Terminal Report) for degraded sections**

Add a conditional:
```
If `cluster_count` is null, replace the corresponding Current State bullet with: `- Cluster detection: skipped (MCP unavailable — see bigeye-mcp-install.md)`.

If `coverage_percent` is `"skipped (MCP unavailable)"`, replace the Coverage bullet with: `- Coverage: skipped (MCP unavailable)`.
```

- [ ] **Step 7: Update Step 5 (Send Slack Notification)**

No change to Slack-send logic (still only sends on critical). Add a note to the template: *"If MCP was unavailable, the Slack template's Coverage line reads `Coverage: n/a (MCP unavailable)`."*

- [ ] **Step 8: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add agents/bigeye-morning-report.md
```

---

## Task 11: Update the router `skills/bigeye/SKILL.md`

**Files:**
- Modify: `skills/bigeye/SKILL.md`

- [ ] **Step 1: Broaden the description field**

In the YAML frontmatter, replace:
```
description: Use when the user mentions BigEye, data quality issues, monitoring gaps, data freshness, monitor coverage, issue triage, root cause analysis, or when BigEye MCP tools are being used in conversation. Routes to the appropriate BigEye sub-skill.
```
with:
```
description: Use when the user mentions BigEye, data quality issues, monitoring gaps, data freshness, monitor coverage, issue triage, root cause analysis, or when BigEye CLI or MCP tools are being used in conversation. Routes to the appropriate BigEye sub-skill.
```

- [ ] **Step 2: Add `cli.md` to the readlist**

Replace the existing "**Before doing anything else**" sentence to also mention `cli.md`.

- [ ] **Step 3: Add a `verify` intent row to the routing table**

In the Routing section, add a new row to the table:
```
| "verify setup", "check config", "is MCP working", "test connection" | Skill: `bigeye-config` with args `verify` |
```

- [ ] **Step 4: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye/SKILL.md
```

---

## Task 12: Create `bigeye-mcp-install.md`

**Files:**
- Create: `bigeye-mcp-install.md`

- [ ] **Step 1: Write the install guide**

Create `bigeye-mcp-install.md` at the repo root with exactly this content:

````markdown
# Bigeye MCP Server — Installation & Setup Guide

Optional companion to the Bigeye CLI. The CLI handles issues, monitor deploys, and table enumeration. The MCP server unlocks these plugin features:

- Root-cause analysis with lineage tracing
- Issue cluster / cascade detection
- Dimension coverage scoring
- Incident creation and management
- Display-number → internal ID lookup (so `/bigeye-rca 10921` works with the number shown in the UI)
- `deployed-by-plugin` tag tracking on created monitors
- Data-source picker in the config wizard

Without MCP, the plugin still runs — you'll see `Note: feature X unavailable — see bigeye-mcp-install.md` warnings on affected skills, and a few operations hard-fail (coverage scoring, incident creation, display-name lookup).

---

## 1. Prerequisites

- Claude Code (you're reading this in it)
- Bigeye account and a **personal access token** (API key from the Bigeye UI — not your CLI password)
- Either `uvx` (recommended, zero-install) OR Python 3.10+ with `pip`

## 2. Install the MCP server

> **TBD during implementation.** Verify the exact published Bigeye MCP package (pip name, source repo, or uvx target) against the current Bigeye docs and fill in two variants here:
>
> **Option A — uvx (zero-install):** single command to point Claude Code at the server without local install.
>
> **Option B — pip/pipx:** long-lived install with a persistent process.

## 3. Register with Claude Code

Add an MCP server entry to your Claude Code MCP config (typically `.mcp.json` in the project root or user-global MCP settings). Example stanza (adjust paths to match whatever you settle on in §2):

```json
{
  "mcpServers": {
    "bigeye": {
      "command": "uvx",
      "args": ["bigeye-mcp"],
      "env": {
        "BIGEYE_API_KEY": "<your-api-key>",
        "BIGEYE_WORKSPACE_ID": "<your-workspace-id>",
        "BIGEYE_BASE_URL": "https://app.bigeye.com"
      }
    }
  }
}
```

Alternatively, read credentials from `~/.bigeye/credentials` if the MCP server supports it — check the server's docs.

Restart Claude Code after editing the config.

## 4. Verify it works

Run:
```
/bigeye-config verify
```

The MCP row should flip to `[✓]` and list the features now enabled.

## 5. Feature matrix

| Plugin feature | CLI | MCP |
|---|---|---|
| List issues, triage summary | yes | — |
| Ack / close individual issues | yes | — |
| Deploy monitors (freshness) | yes | — |
| Deploy monitors (gaps / bulk) | yes | **required (coverage scoring)** |
| Root-cause lineage trace | — | **required** |
| Issue cluster detection | — | **required** |
| Dimension coverage scoring | — | **required** |
| Incident creation | — | **required** |
| Display-name → internal-ID lookup | — | **required** |
| `deployed-by-plugin` tagging | — | **required** |

## 6. Troubleshooting

**`/bigeye-config verify` shows `[!] MCP server reachable`** — server registered but unreachable. Check:
- MCP server process is running (for pip/pipx installs)
- API key and workspace ID are correct
- `BIGEYE_BASE_URL` matches your Bigeye deployment (not always `app.bigeye.com`)

**`401 Unauthorized` from MCP** — API key is wrong or expired. Regenerate in the Bigeye UI (Settings → Personal access tokens). Note: this is separate from the `~/.bigeye/credentials` used by the CLI.

**`uvx` cold-start is slow** — first call to an uvx-launched MCP server downloads the package. Subsequent calls are fast.

**The plugin still shows MCP warnings after registering** — run `/bigeye-config verify`; if it still reports MCP unreachable, check Claude Code's MCP logs (usually in the status bar or via `/mcp` command).
````

- [ ] **Step 2: Verify file length and headings**

Run:
```bash
head -5 /Users/andriik-mbp/PycharmProjects/bigeye-plugin/bigeye-mcp-install.md
grep -c '^##' /Users/andriik-mbp/PycharmProjects/bigeye-plugin/bigeye-mcp-install.md
```

Expected: first line is `# Bigeye MCP Server — Installation & Setup Guide`; at least 6 `##` section headings.

- [ ] **Step 3: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add bigeye-mcp-install.md
```

---

## Task 13: Update `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the Requirements section**

Replace:
```
## Requirements

- Claude Code with plugin support
- BigEye MCP server configured and authenticated
- Slack MCP server (optional, for morning report notifications)
```
with:
```
## Requirements

- Claude Code with plugin support
- **Bigeye CLI 0.7+** installed and authenticated — see [`bigeye-cli-install.md`](bigeye-cli-install.md)
- **Bigeye MCP server** (optional; unlocks RCA lineage, coverage scoring, incident creation, cluster detection, display-name lookup, and tag tracking) — see [`bigeye-mcp-install.md`](bigeye-mcp-install.md)
- Slack MCP server (optional, for morning report notifications)
```

- [ ] **Step 2: Add a "How it works" subsection**

After the Requirements section, add:
```
## How it works

Every BigEye skill uses the CLI as its primary transport. If the MCP server is also configured, advanced features (lineage, clustering, coverage scoring, incidents) become available transparently. If MCP is not configured, skills still run — affected features print a one-line note pointing at `bigeye-mcp-install.md`.

Run `/bigeye-config verify` at any time to see which features are enabled.
```

- [ ] **Step 3: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add README.md
```

---

## Task 14: Update `hooks/hooks.json` SessionStart message

**Files:**
- Modify: `hooks/hooks.json`

- [ ] **Step 1: Replace the message**

Open `hooks/hooks.json`. Replace the `message` field:

Before:
```
"message": "BigEye Data Observability plugin is active. Available commands: /bigeye, /bigeye-triage, /bigeye-rca, /bigeye-coverage, /bigeye-deploy, /bigeye-incidents. Say /bigeye to get started."
```
After:
```
"message": "BigEye Data Observability plugin is active. CLI: required. MCP: optional (enables lineage, coverage, incidents). Run /bigeye-config verify to check setup, or /bigeye to get started."
```

- [ ] **Step 2: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add hooks/hooks.json
```

---

## Task 15: Version bump

**Files:**
- Modify: `.claude-plugin/marketplace.json`
- Modify: `pyproject.toml`

- [ ] **Step 1: Bump marketplace.json**

In `.claude-plugin/marketplace.json`, change `"version": "0.1.0"` to `"version": "0.2.0"`.

- [ ] **Step 2: Bump pyproject.toml**

In `pyproject.toml`, change `version = "0.1.0"` to `version = "0.2.0"`.

- [ ] **Step 3: Verify**

Run:
```bash
grep -E '"version"|^version' /Users/andriik-mbp/PycharmProjects/bigeye-plugin/.claude-plugin/marketplace.json /Users/andriik-mbp/PycharmProjects/bigeye-plugin/pyproject.toml
```

Expected: both show `0.2.0`.

- [ ] **Step 4: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add .claude-plugin/marketplace.json pyproject.toml
```

---

## Task 16: Cross-reference verification

**Files:**
- Read-only check across the whole repo

- [ ] **Step 1: Confirm every skill reads `cli.md`**

Run:
```bash
grep -rL 'cli.md' /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/*/SKILL.md /Users/andriik-mbp/PycharmProjects/bigeye-plugin/agents/
```

Expected: empty output (every file contains `cli.md`). If any file is listed, revisit its task.

- [ ] **Step 2: Confirm no lingering MCP-only references where CLI should be primary**

Run:
```bash
grep -rn 'mcp__bigeye__list_issues' /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/ /Users/andriik-mbp/PycharmProjects/bigeye-plugin/agents/
```

Expected: zero matches (all listing now goes through `bigeye issues get-issues`).

- [ ] **Step 3: Confirm closing-label vocab is updated**

Run:
```bash
grep -rn 'METRIC_RUN_LABEL' /Users/andriik-mbp/PycharmProjects/bigeye-plugin/
```

Expected: zero matches.

- [ ] **Step 4: Confirm no stray `tags` scope field**

Run:
```bash
grep -rn '"tags":' /Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/ /Users/andriik-mbp/PycharmProjects/bigeye-plugin/agents/
```

Expected: zero matches (the tag field is removed from schema and examples; narrative mentions in bigeye-config migration section are ok, and can be separately verified).

- [ ] **Step 5: If all checks pass, no further staging needed**

This task is verification-only. If any grep reveals issues, fix them in the relevant skill file and re-run the check.

---

## Task 17: Manual validation checklist

**Files:**
- None (manual scenarios run against a real Bigeye workspace)

This task is the human sign-off. Run each scenario with both (a) MCP enabled and (b) MCP disabled — see spec §8.3 for MCP-absence simulation.

- [ ] **Config wizard**
  - `/bigeye-config init` on a fresh machine writes both `~/.claude/bigeye-plugin/profiles.json` AND `~/.bigeye/config.ini`
  - `/bigeye-config init` with pre-existing `~/.bigeye/config.ini` leaves unknown sections intact
  - `/bigeye-config add <name>` on existing profiles.json with a `tags` field strips tags and prints the migration notice once per session
  - `/bigeye-config delete <name>` removes both files with explicit CLI-section confirmation
  - Profile name with spaces (`/bigeye-config add "bad name"`) is rejected
  - `/bigeye-config verify` prints correct `[✓]`/`[!]`/`[✗]` for all four checks

- [ ] **Triage**
  - `/bigeye-triage` with MCP reachable matches current output format
  - Same with MCP disabled: output still renders; Summary's cluster line reads `Cluster detection disabled — MCP not configured (see bigeye-mcp-install.md)`
  - `/bigeye-triage new` filters to `ISSUE_STATUS_NEW` only
  - Scope with warehouse filter narrows the CLI call's `-wid` argument; result is correctly scoped
  - Empty scoped result: `No active issues in scope 'X' — all clear.`

- [ ] **RCA**
  - `/bigeye-rca 10921` (display number) with MCP: full RCA
  - Same with MCP absent: hard-fails with the pointer to `--internal-id`
  - `/bigeye-rca 4472 --internal-id` with MCP absent: issue details render; Lineage/Related/Resolution sections each say `(skipped — MCP unavailable)`; banner `Reduced RCA — MCP unavailable` appears after Scope header
  - `/bigeye-rca 99999` (not found) gives a useful error

- [ ] **Coverage**
  - `/bigeye-coverage` with MCP present: full report
  - Same with MCP absent: hard-fails with pointer to `bigeye-mcp-install.md`; no reduced report shown
  - `/bigeye-coverage dimension freshness` filter works when MCP present

- [ ] **Deploy**
  - `/bigeye-deploy gaps` with MCP: bigconfig YAML written, plan shown, apply creates monitors; `deployed-by-plugin` tag visible in Bigeye UI
  - `/bigeye-deploy freshness` with MCP: monitor created and tagged
  - `/bigeye-deploy columns email,name` with MCP present: inferred dimensions drive metric type
  - `/bigeye-deploy gaps` with MCP absent: hard-fails
  - `/bigeye-deploy freshness` with MCP absent: monitor created; output includes tagging-skipped note
  - `/bigeye-deploy columns email --metric-type PERCENT_NULL` with MCP absent: monitor created; tagging skipped
  - `/bigeye-deploy columns email` (no `--metric-type`) with MCP absent: hard-fails with pointer
  - `edit` at the plan confirmation gate re-renders the plan

- [ ] **Incidents**
  - `/bigeye-incidents 10919 10920 10921` (display numbers) with MCP: incident created; visible in UI
  - `/bigeye-incidents 4470 4471 4472 --internal-id` with MCP absent: hard-fails on incident creation with pointer
  - `/bigeye-incidents close 10921 --label true-negative` with MCP: resolves display → internal → CLI `update-issue -cl TRUE_POSITIVE`
  - `/bigeye-incidents close 4472 --internal-id --label false-positive` with MCP absent: works; issue closed with `FALSE_POSITIVE`
  - `/bigeye-incidents auto` with MCP: clusters detected, incidents created on confirmation

- [ ] **Morning report (agent)**
  - Scheduled run with MCP present: full Slack message including Coverage and Cluster sections
  - Scheduled run with MCP absent: CLI-only report; Slack fires on criticals with sections replaced by `skipped — MCP unavailable` notes
  - Missing `~/.claude/bigeye-plugin/profiles.json` in a scheduled run: agent prints the existing clean error and exits

- [ ] **Cross-cutting**
  - After a representative run, `/tmp/bigeye-*` is empty (no lingering tempdirs)
  - Induce a parse failure (e.g., truncate a CLI output file) and confirm the tempdir is preserved and its path is printed
  - Grep a full scenario pass's transcript for non-ASCII: only the `[✓]` marker appears (no other non-ASCII)
  - `/bigeye-config verify` runs in under 3 seconds with MCP reachable; under 5 seconds when MCP is absent (timeout path)

- [ ] **Sign-off**
  - All scenarios above pass with no unexpected errors or output deviations
  - Notify the user; ready to commit + ship
