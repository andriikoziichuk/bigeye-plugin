# BigEye Plugin — Scope Configuration

**Date:** 2026-04-16
**Status:** Approved design, ready for implementation plan

## Problem

Every BigEye skill in this plugin (`/bigeye-triage`, `/bigeye-rca`, `/bigeye-coverage`, `/bigeye-deploy`, `/bigeye-incidents`) currently calls BigEye MCP tools unscoped — it returns whatever the authenticated MCP credentials can see. For users who work with a focused slice of the catalog (one physical table, a data source holding a handful of monitors, a few virtual tables), this floods output with irrelevant issues from the rest of the workspace.

**Goal:** let each user configure persistent, per-user scope — workspace plus optional filters by data source, table, schema, and tag — and have every skill apply that scope automatically.

## Scope of this spec

In scope:
- A per-user profiles file (multiple named profiles, one default).
- A new user-invocable skill `bigeye-config` that owns wizard / show / switch / add / edit / delete.
- A shared reference doc `skills/bigeye/references/scope.md` that teaches every other skill how to consume the config.
- Small edits to the five existing skills and the morning-report agent so they read scope.
- Override flags (`--profile`, `--no-scope`, `--workspace`) usable on every skill.

Out of scope:
- Any change to the BigEye MCP server itself.
- Automated test harness (verification is a manual checklist — see Verification section).
- Syncing profiles across machines.

## Architecture

```
                           +-------------------------+
                           |  /bigeye-config         |
                           |  (wizard, show,         |
                           |   switch, add, edit)    |
                           +-----------+-------------+
                                       | writes
                                       v
  ~/.claude/bigeye-plugin/profiles.json   (per-user, not committed)
                                       ^
                                       | read at start of every skill
                                       |
  skills/bigeye/references/scope.md   (tells each skill HOW to read
                                        and apply the active profile)
                                       ^
                                       | referenced by
                                       |
  /bigeye-triage   /bigeye-rca   /bigeye-coverage
  /bigeye-deploy   /bigeye-incidents   bigeye-morning-report
```

One source of truth for scope logic (`scope.md`). One source of truth for the data (profiles.json). Every skill is thin: it adds one "read scope.md" line and one "apply scope" step.

## Config file

**Location:** `~/.claude/bigeye-plugin/profiles.json`

Kept in its own directory (not shared with other plugins' settings), per-user, git-ignored by virtue of being outside the repo. Survives plugin reinstalls.

**Schema:**

```json
{
  "default_profile": "work-area",
  "profiles": {
    "work-area": {
      "workspace_id": 42,
      "data_source_ids": [17],
      "table_ids": [],
      "table_names": ["orders_main", "orders_virtual_recent", "orders_virtual_ltv"],
      "schema_names": [],
      "tags": []
    },
    "full-view": {
      "workspace_id": 42
    }
  }
}
```

**Field rules:**
- `default_profile` (required): must reference a key in `profiles`.
- Each profile requires `workspace_id`. All other fields are optional.
- When multiple filter fields are set, they are combined as a union (OR) — the skill requests issues matching any of the configured scopes.
- A profile with only `workspace_id` means "whole workspace" (e.g., `full-view` above).

## The `bigeye-config` skill

Location: `skills/bigeye-config/SKILL.md`. User-invocable as `/bigeye-config`.

This is the **only** skill that writes `profiles.json`.

**Subcommands** (parsed from `$ARGUMENTS`):

| Invocation | Behavior |
|---|---|
| `/bigeye-config` or `/bigeye-config show` | Print active profile name + all profiles in a table |
| `/bigeye-config init` | Run wizard, write profile, set as default. If file exists, ask whether to overwrite or add |
| `/bigeye-config add <name>` | Run wizard, add a new profile without changing the default |
| `/bigeye-config switch <name>` | Set `default_profile` to `<name>` (fail if name missing) |
| `/bigeye-config edit <name>` | Re-run wizard against an existing profile |
| `/bigeye-config delete <name>` | Remove a profile. Refuse if it is the default and no alternative exists |

**Wizard flow:**
1. Ask for `workspace_id`. Optionally call `mcp__bigeye__list_data_sources` to confirm the workspace is reachable.
2. "Filter by data source?" — if yes, list sources via `mcp__bigeye__list_data_sources`, let user pick one or more IDs.
3. "Filter by specific tables?" — if yes, ask names. Help the user convert names → IDs using whatever catalog-browsing MCP tools are available (`mcp__bigeye__list_tables`, or `mcp__bigeye-knowledgebase__*` tools if that server is also installed). Store both `table_names` and resolved `table_ids` when possible.
4. "Filter by schema?" — optional.
5. "Filter by tags?" — optional (user may skip; tags are supported but not expected to be common).
6. Show a summary. Confirm. Write the file.

**Auto-trigger on missing config:** `scope.md` instructs every other skill to check for `profiles.json` first; if missing, invoke `bigeye-config init` and then resume.

## Shared `scope.md` reference

Location: `skills/bigeye/references/scope.md`.

Every existing SKILL.md updates its "Before doing anything else" line to read **both** `conventions.md` **and** `scope.md`.

`scope.md` contents (what it tells Claude to do at the start of every skill invocation):

1. **Load profile.**
   - Read `~/.claude/bigeye-plugin/profiles.json`.
   - If missing → invoke `bigeye-config` skill with arg `init`, then re-read.
   - If the skill's `$ARGUMENTS` include `--profile <name>`, use that profile. Otherwise use `default_profile`.

2. **Parameter mapping** (for `mcp__bigeye__list_issues` and other filterable tools):

   | Profile field | MCP parameter |
   |---|---|
   | `workspace_id` | `workspace_id` |
   | `data_source_ids` | `data_source_ids` (exact name confirmed at implementation — fall back to `source_ids` if that is what the MCP uses) |
   | `table_ids` + resolved `table_names` | `table_ids` |
   | `schema_names` | `schema_names` |
   | `tags` | `tags` |

   Omit any parameter whose field is empty.

3. **Scope applicability per skill** (authoritative — so the LLM doesn't have to guess):

   | Skill | Scope applies to |
   |---|---|
   | `bigeye-triage` | `list_issues` call — fully scoped |
   | `bigeye-coverage` | Table enumeration — only in-scope tables are scanned |
   | `bigeye-deploy` | Only operate on in-scope tables unless the user names a target explicitly |
   | `bigeye-incidents` | Issue listing + auto-cluster detection — fully scoped |
   | `bigeye-rca` | Primary issue lookup by ID is **unscoped**. Scope applies only to lineage expansion and related-issue search |

4. **Override flags** (each skill parses these from `$ARGUMENTS`, ahead of its own args):
   - `--profile <name>` — use a different profile for this invocation.
   - `--no-scope` — run unscoped (workspace-wide); `workspace_id` from the active profile is still applied.
   - `--workspace <id>` — override `workspace_id` for this call only.

5. **Name → ID resolution.** Resolve `table_names` (and similar) to IDs **once** at the start of the invocation via `search_metadata` / `list_tables`. If a configured name resolves to zero tables, print a warning in the Scope header (e.g., `tables=2/3 (1 unresolved: "orders_virtual_ltv")`) but continue with what resolved — a table could have been renamed.

6. **Transparency requirement.** Every skill's output MUST start with a one-line `Scope:` header, e.g.:

   ```
   Scope: profile=work-area · workspace=42 · tables=3 · sources=1
   ```

   When `--no-scope` is used: `Scope: profile=work-area · NO-SCOPE (override)`.

7. **Empty-result phrasing.** When a scoped call returns zero results, skills should say `"No active issues in scope '<profile>' — all clear."` instead of the current generic message, so users don't confuse "nothing to see here" with "scope hid everything."

## Per-skill changes

Each of the five existing skills (`bigeye-triage`, `bigeye-rca`, `bigeye-coverage`, `bigeye-deploy`, `bigeye-incidents`) and `bigeye-morning-report.md` gets small, mechanical edits:

- Update the "Before doing anything else" instruction to read both `conventions.md` and `scope.md`.
- Insert one new step before the first MCP call: "apply scope filters per `scope.md`."
- Insert the `Scope:` header as the first line of output.
- (RCA only) Add the soft notice text for out-of-scope primary issues.

No logic changes beyond that — `scope.md` is the single source of truth.

## Morning report agent

`agents/bigeye-morning-report.md` also applies scope, using the default profile. If a user wants a different profile for the scheduled run, they update the cron command to pass `--profile <name>` to the agent invocation. This means each user's scheduled report only covers their own area.

## Edge cases

**Missing / invalid config:**
- File missing → auto-run `bigeye-config init`.
- Malformed JSON → skill stops, prints parse error, suggests `/bigeye-config init` to recreate.
- `default_profile` points to a missing name → skill stops, lists available profiles, asks user to pick one.
- Profile has no `workspace_id` → treated as invalid; same error path.

**Override composition** (flags act on different dimensions — they compose rather than strictly override):
- `--profile <name>` selects *which* profile is active for this invocation; without it, `default_profile` wins.
- `--no-scope` clears the filter fields (data sources, tables, schemas, tags) but keeps the profile's `workspace_id`.
- `--workspace <id>` replaces the `workspace_id` for this call only, regardless of profile.
- All three can be combined, e.g. `--profile full-view --no-scope --workspace 99` means "unscoped query in workspace 99."

**Out-of-scope RCA:** `/bigeye-rca <id>` where `<id>` is outside the current scope runs normally but prints a soft notice: `Note: issue <id> is outside the current scope '<profile>'`. Scope still filters the lineage expansion and related-issue search.

**Unresolvable `table_names`:** warning in the Scope header, not a hard fail.

## Verification (manual checklist, to be included in the plan)

No automated runner. Each item executed by hand against a real BigEye workspace:

**Wizard:**
- Fresh install, no config file → any skill invocation triggers `bigeye-config init` → profile written → original skill continues.
- `/bigeye-config init` when a file already exists → asks whether to overwrite or add.
- `/bigeye-config add`, `switch`, `show`, `delete` each round-trip correctly.

**Scope application:**
- `/bigeye-triage` with `work-area` profile → Scope header correct → issue list limited to in-scope issues.
- `/bigeye-triage --no-scope` → Scope header shows NO-SCOPE → full-workspace results.
- `/bigeye-triage --profile full-view` → uses the alternate profile.
- `/bigeye-coverage` → only enumerates in-scope tables.
- `/bigeye-rca <in-scope-id>` → runs normally, related issues scope-limited.
- `/bigeye-rca <out-of-scope-id>` → runs with soft notice, still analyzes.

**Error paths:**
- Malformed JSON → clean error message, no silent failure.
- `default_profile` pointing to missing name → lists profiles, asks user to pick.
- `table_names` with one unresolvable entry → warning in Scope header, skill continues.

## Non-goals / deferred

- Encrypting or otherwise protecting profile contents (workspace IDs are not secrets).
- Syncing profiles across multiple machines.
- Any UI beyond slash commands.
- Profile versioning / migration tooling — if the schema changes later, `bigeye-config init` will be the migration path.
