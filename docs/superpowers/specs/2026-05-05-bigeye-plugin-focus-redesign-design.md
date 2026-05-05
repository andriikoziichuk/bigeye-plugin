# BigEye Plugin — Focus Redesign (v0.5.0)

**Date:** 2026-05-05
**Status:** Spec — pending implementation plan
**Supersedes:** 2026-04-24 UX redesign (0.4.0) for the three pillars below; other 0.4.0 surface stays as hidden-but-callable.

## Goal

Narrow the plugin's user-facing surface to three pillars and an ambient documentation-grounding capability. Other features remain on disk and callable, but are removed from README, help text, and skill discovery.

The three pillars:

1. **Roster routine** — daily, advisory loop over open BigEye issues in the user's profile scope. Plugin gathers facts per issue, presents a recommendation, and the user picks the action. No silent auto-close, no learned auto-dismiss.
2. **Improve a single monitor** — read-only, hard-mode recommendation for one monitor, grounded in profile data and validated with SQL.
3. **Batch coverage proposal** — interactive, per-column conversation with the user about what the column actually holds, then a fitted set of recommended monitors per column.

Plus an ambient grounding layer: whenever the plugin explains a monitor type, dimension, threshold semantic, or coverage concept, it fetches BigEye documentation and cites the URL.

The plugin is **MCP-only** for these pillars. The BigEye CLI is hidden — install doc remains on disk, but is not referenced from the README or skill help.

## Non-goals

- Re-implementing or replacing the existing CLI install path on disk; only its visibility changes.
- Auto-deploying any monitor change. Improve and coverage emit proposals; the user runs `/bigeye-deploy` (hidden, callable) to apply.
- Auto-learning flaky patterns or auto-closing recurring issues. The plugin only proposes; the user decides every action.
- Removing already-shipped commands. They are kept on disk and remain callable (escape hatch for power users).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ User                                                         │
└──────┬─────────────────┬─────────────────┬──────────────────┘
       │                 │                 │
       ▼                 ▼                 ▼
 /bigeye-roster   /bigeye-improve   /bigeye-coverage
 (daily routine)  <monitor>         <table>
       │           (single, hard     (interactive batch
       │            mode + SQL)       per-column)
       │                 │                 │
       └────────┬────────┴────────┬────────┘
                ▼                 ▼
       ┌────────────────┐  ┌──────────────────┐
       │  Profile +     │  │ Doc grounding    │
       │  custom hints  │  │ (ambient skill,  │
       │  (config skill)│  │  WebFetch + cite)│
       └────────┬───────┘  └────────┬─────────┘
                ▼                   ▼
        ┌──────────────────────────────────┐
        │ MCP (required for all 3 pillars) │
        └──────────────────────────────────┘
```

Principles:

- **Advisory only.** Plugin proposes, user acts.
- **MCP required.** No CLI fallback for these pillars. CLI install stays on disk, hidden from docs.
- **Profile = scope + hints.** Hints are advisory inputs to the roster analyzer, never silently applied.
- **Doc grounding is ambient.** Not a slash command — a skill the model auto-invokes whenever explaining a BigEye concept, citing the URL inline.
- **Hidden skills stay callable.** `/bigeye-rca`, `/bigeye-today`, `/bigeye-table`, `/bigeye-triage`, `/bigeye` (dashboard), `/bigeye-incidents`, `/bigeye-ticket`, `/bigeye-deploy` are removed from README and skill descriptions but remain on disk and invocable directly.

## Components

| Component | Responsibility | Status |
|---|---|---|
| `bigeye-config` | CRUD profiles + custom hints. New subcommands: `hints add/edit/delete/list`, `virtual-tables add/edit/delete`. Resolves names → IDs at add-time via MCP. | Existing, extended |
| `bigeye-roster` | Daily routine. Iterates open issues in scope; gathers facts; renders recommendation; user picks action; logs to `state.json`. | NEW |
| `bigeye-improve` | Single-monitor mode: `/bigeye-improve <monitor_id>`. Hard mode + SQL refinement loop. Read-only proposal. Existing table-mode kept on hidden surface. | Existing, extended |
| `bigeye-coverage` | Interactive batch proposal. Per uncovered column, plugin shows profile data, asks user what the column holds, recommends fitted monitors. Read-only. | Existing, rewritten |
| `bigeye-docs-grounding` | Ambient skill. Auto-invokes whenever the model explains a BigEye monitor, dimension, threshold semantic, or coverage concept. Uses WebFetch on docs base URL and cites the URL inline. | NEW |
| Settings | New keys: `docs.base_url` (default `https://docs.bigeye.com`), `roster.max_facts_per_issue` (default 6), `roster.batch_size` (default 5). | Extended |

## Profile schema

`~/.claude/bigeye-plugin/profiles.json`:

```json
{
  "active_profile": "prod",
  "profiles": {
    "prod": {
      "workspace_id": 123,
      "scope": {
        "data_sources":   [{"id": 12, "name": "snowflake_prod"}],
        "schemas":        [{"id": 34, "name": "analytics"}],
        "tables":         [{"id": 101, "name": "orders"},
                           {"id": 102, "name": "users"}],
        "virtual_tables": [{"id": 55, "name": "active_users_30d"}]
      },
      "monitored_rules": [{"id": 1, "name": "freshness"},
                          {"id": 4, "name": "row_count"}],
      "custom_hints": [
        {
          "scope": "table",
          "target_id": 101,
          "target_name": "orders",
          "raw": "ignore deltas under 2% on row count",
          "compiled": {
            "type": "noise_threshold",
            "metric": "row_count",
            "delta_pct_max": 2.0
          },
          "created_at": "2026-05-05T10:00:00Z"
        }
      ]
    }
  }
}
```

**Storage rules:**

- All scope refs and `monitored_rules` stored as `{id, name}` pairs. ID is the stable key; name is for display.
- At add-time, user types a name; plugin MCP-searches; if a single match exists, plugin saves `{id, name}`; if multiple matches exist, plugin lists candidates with IDs and asks the user to pick.
- `custom_hints[*].compiled` is one of three shapes:
  - `noise_threshold` — `{type, metric, delta_pct_max}` — analyzer surfaces "user-defined noise floor: X%" as a fact and compares against current delta.
  - `context` — `{type, text}` — analyzer surfaces text verbatim as a fact.
  - `expected_pattern` — `{type, when, metric}` — analyzer matches issue timestamp against pattern (e.g. weekend, weekday, hour-of-day) and surfaces "matches expected pattern" as a fact.

**Hint authoring flow** (`/bigeye-config hints add`):

1. User types NL: `"ignore deltas under 2% on row count for orders"`.
2. Plugin (Claude) parses → emits compiled predicate JSON.
3. Plugin shows compiled form → asks confirm.
4. On confirm → save `{raw, compiled, created_at}` together.
5. If parse is ambiguous → ask follow-up clarifier. Refuse to save raw without a compiled form.

## Data flow — `/bigeye-roster` (daily routine)

```
1. Load active profile (or --profile <name>).
2. MCP list_issues filtered by scope (workspace + table_ids + monitored_rules).
3. For each issue, ordered by severity desc then opened_at:
   a. Gather facts (parallel where possible):
      - Current metric value vs threshold              (MCP get_issue)
      - Last N runs / trend                            (MCP list_table_metrics history)
      - Recurrence count, 90d window                   (MCP search_issues by monitor_id)
      - Matching custom hints                          (local profile lookup)
      - Profile drift signal                           (MCP get_table_profile delta)
   b. Derive recommendation (LLM reasoning over facts).
   c. Render: facts list + recommendation + actions menu.
   d. User picks action. Plugin executes. Logs {issue_id, action, reason, ts} to state.json.
4. Pacing: process in batches of roster.batch_size (default 5). Show batch summary, ask continue/stop.
5. Resumable: next run skips already-actioned issues unless --include-actioned.
6. End-of-pass summary: N reviewed, X closed, Y tickets, Z improvements queued, W flaky-noted.
```

**Render template:**

```
[Issue #1234 — orders.created_at freshness, severity HIGH]
Facts:
  • Metric 4.2h vs threshold 4h (5% over, stable 3d)
  • Last 30d: fired 7×, all 3-5% over
  • Custom hint (orders): "ignore <2% delta on row_count" — not applicable here
Recommendation: persistent small-delta — likely threshold tight.
                Suggest /bigeye-improve <monitor_id>.
                Source: https://docs.bigeye.com/...freshness-thresholds
Action? [c]lose  [f]laky-note  [t]icket  [i]mprove  [h]int  [s]kip
```

**Action handlers:**

| Key | Action | Implementation |
|---|---|---|
| c | Close issue with user-supplied reason | MCP `update_issue(status=CLOSED, reason)` |
| f | Mark flaky note (no future learning) | MCP `update_issue` + note tag |
| t | Render markdown ticket | Reuse hidden `/bigeye-ticket` rendering, output to terminal |
| i | Jump to single-monitor improve | Suggest `/bigeye-improve <monitor_id>` (or chain via subagent) |
| h | Add custom hint to profile | NL → compile → confirm → save → re-evaluate facts |
| s | Skip | Log skip, continue |

## Data flow — `/bigeye-improve <monitor_id>` (single, hard mode)

```
1. Resolve monitor: MCP get monitor by ID → metric type, current threshold, table, column.
2. Gather profile data:
   - MCP get_table_profile(table_id)            — column stats, distribution.
   - MCP list_table_metrics(table_id) history   — recent runs of this metric.
   - Custom hints scoped to this monitor/table  — local.
3. Generate candidate change (LLM reasoning):
   - Threshold metrics: propose new bounds based on observed distribution + history.
   - Regex / categorical: propose tightened pattern grounded in actual values.
4. SQL refinement loop (hard mode, up to 3 iterations):
   - Emit candidate SQL that would fail with proposed threshold against last 30d data.
   - Run via MCP → count false-positive / false-negative.
   - Adjust candidate.
5. Render proposal with reasoning, supporting SQL, FP/FN counts, doc citation, and the `/bigeye-deploy` command the user can run to apply it.
6. Read-only output. User runs deploy separately.
```

## Data flow — `/bigeye-coverage <table>` (interactive, data-aware)

```
1. Resolve table → table_id (MCP search_lineage_nodes / list_tables; ambiguity → user picks).
2. MCP get_table_profile(table_id) → per-column profile (null %, distinct count, cardinality,
                                                         format samples, numeric/length stats).
3. MCP get_table_dimension_coverage(table_id) → which monitors already exist.
4. For each uncovered or weakly-covered column, in priority order (PK/FK first), in batches of 3:
   a. Show user the auto-detected profile (sample values, format, stats).
   b. Ask user: "What does this column hold? (auto-guess: …) — confirm / specify / skip".
   c. User confirms or refines (e.g. "yes — work emails only, must be @company.com").
   d. Plugin maps user answer + profile → fitted monitor candidates (with reasoning + doc citation).
   e. User picks which to queue.
5. Aggregate queued → render bulk deploy block:
       /bigeye-deploy gaps <table> --queued
6. Read-only. User runs deploy separately.
7. Resumable: state saved per column. /bigeye-coverage no-arg resumes from last column.
```

## Doc grounding (ambient)

Mechanism: a skill `bigeye-docs-grounding` whose description tells the model to auto-invoke whenever it is about to explain a BigEye monitor type, dimension, threshold semantic, coverage concept, or any BigEye behavior.

When invoked:

1. WebFetch `settings.docs.base_url` (default `https://docs.bigeye.com`) for the relevant page.
2. Extract the relevant section.
3. Return the answer + cite the URL inline. Always end with `Source: <url>`.
4. On WebFetch failure: answer best-effort + flag `(docs unreachable — no citation)`. Never blocks the parent skill.

This layer is used by all three pillars whenever they explain a monitor recommendation, threshold change, or dimension gap.

## Error handling

MCP is required for all three pillars.

| Case | Behavior |
|---|---|
| MCP unreachable | Hard-fail. Output: `MCP unreachable. Try /mcp reconnect bigeye, then retry. See bigeye-mcp-install.md if it persists.` |
| MCP auth failed | `MCP auth failed. Run /bigeye-config verify, refresh token in env, then /mcp reconnect bigeye.` |
| MCP rate-limit / per-call timeout | Inline retry once. On second failure: surface `Bigeye API timed out. Retry, or check bigeye-mcp-install.md`, skip the current item, continue the loop. |
| `profiles.json` missing | Auto-invoke `/bigeye-config init`, resume calling command. |
| `active_profile` set, missing in file | Error + `Fix: /bigeye-config switch <name>` + list available profiles. |
| Stale ID in profile (table/monitor deleted in BigEye) | Per-item skip with warn. End-of-pass prompt: `Stale entries found in profile. Run /bigeye-config tables remove <name>.` |
| Hint NL ambiguous | Don't save. Ask follow-up clarifier. Refuse save without compiled form. |
| Action write fails (close / flaky / hint save) | Standard Error/Fix/Why block. Issue stays open. Continue to next on user confirm. |
| WebFetch fails (doc grounding) | Answer best-effort + flag `(docs unreachable — no citation)`. Never blocks parent skill. |
| `state.json` parse fail | Rename to `state.json.broken-<ts>`, start fresh, log rename. Never block startup. |

## Settings additions

`~/.claude/bigeye-plugin/settings.json`:

```json
{
  "docs": { "base_url": "https://docs.bigeye.com" },
  "roster": {
    "batch_size": 5,
    "max_facts_per_issue": 6
  }
}
```

Existing keys (`slack.channel`, `severity.*`, `deploy.*`, `default_view`) are unchanged.

## Visibility changes (README + skill descriptions)

Removed from README and from skill `description` fields (kept on disk, callable):

- `/bigeye` (dashboard)
- `/bigeye-today`
- `/bigeye-table`
- `/bigeye-triage`
- `/bigeye-rca`
- `/bigeye-incidents`
- `/bigeye-ticket`
- `/bigeye-deploy`

Kept on the user-facing surface:

- `/bigeye-roster`     — daily routine (NEW)
- `/bigeye-improve`    — single-monitor mode highlighted; table mode hidden
- `/bigeye-coverage`   — interactive batch proposal
- `/bigeye-config`     — extended for hints + virtual tables + name→id resolution

CLI install reference (`bigeye-cli-install.md`) is removed from the README. The file stays on disk for users who land there directly.

## Testing

### Schema validation (automated)

Lightweight script `tests/validate_schema.py`:

- `profiles.json` — required keys per profile; `scope.*` arrays of `{id, name}`; `monitored_rules` shape; `custom_hints[*].compiled` matches one of three known shapes; ISO timestamps parse.
- `settings.json` — required keys present and typed (including new `docs.base_url`, `roster.batch_size`, `roster.max_facts_per_issue`).
- `state.json` — optional. If present, parses; tolerates missing keys.

### Hint compilation tests (automated)

`tests/fixtures/hints.json` holds `{raw, expected_compiled}` pairs. Test compiles each `raw` through the hint-authoring prompt and asserts JSON-equality.

### Skill discovery checklist (manual)

`tests/skill-discovery.md` lists trigger phrases and the skill that should auto-invoke for each. Exercised at session start by typing each phrase.

### Scenario walkthroughs (manual)

`tests/scenarios.md`:

1. Roster happy path — exercise each action (close, flaky-note, ticket, improve, hint, skip).
2. Roster MCP down — verify reconnect hint.
3. Improve happy path — proposal cites docs URL, shows SQL + FP/FN counts.
4. Coverage interactive — per-column data prompt, fitted monitors, doc citation.
5. Profile add by name — single match auto-saves; multiple matches prompt to pick.
6. Hint NL ambiguous — clarifier loop runs; save refused without compile.
7. Doc grounding offline — fallback message printed, parent skill continues.

### Out of scope

- Unit-testing LLM reasoning (recommendation derivation, hint compilation correctness beyond fixture coverage).
- End-to-end deploy tests — `/bigeye-deploy` is hidden surface.

## Migration

- **Profile file:** existing `profiles.json` parses unchanged. New optional keys (`virtual_tables`, `monitored_rules`, `custom_hints`) default to empty arrays when absent. Schema validator tolerates missing keys.
- **Settings file:** new keys (`docs.base_url`, `roster.*`) seeded with defaults on first run after upgrade if missing.
- **State file:** unchanged.
- **README + skill descriptions:** rewritten in this release. Hidden commands keep their `SKILL.md` files but their descriptions no longer mention them as user-facing entry points.
- **CLI install doc:** unreferenced from README; file remains on disk.

## Open questions

None blocking implementation. Items that may surface during the implementation plan:

- Exact MCP tool names for "monitor by id" lookup vs "list monitors for table" — needs verification against the bigeye MCP server's current tool list.
- Compiled-hint schema may grow a fourth type (e.g. `severity_floor`) once the roster is exercised against real noisy issues.
- Coverage's "what does this column hold" question may benefit from a small fixed taxonomy (email / id / categorical / numeric range / timestamp / freeform text) to constrain the user's free-text input — defer until after first scenario walkthrough.
