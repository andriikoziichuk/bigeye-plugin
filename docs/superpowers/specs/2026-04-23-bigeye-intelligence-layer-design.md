# BigEye Plugin — Intelligence Layer (Ticket + Improve)

**Date:** 2026-04-23
**Status:** Approved design — ready for implementation planning
**Author:** Andrii Koziichuk (with Claude Code)
**Supersedes / depends on:** `2026-04-23-bigeye-cli-migration-design.md` (this design assumes the CLI-first architecture is in place)

---

## 1. Motivation

The BigEye plugin today is read-capable and action-capable (triage, RCA, coverage, deploy, incidents) but offers little *intelligence* on top of the data. Three gaps in the team's day-to-day workflow:

1. **Vendor tickets are re-authored from scratch every time.** When BigEye surfaces bad data, the team drafts a Service Request to the external data vendor. Today that's copy-paste + manual formatting. There is no reusable template, no standard variable set, no way to swap templates per vendor.
2. **Existing monitors drift.** A `VALID_REGEX` like `.+@.+` catches almost nothing useful. A `FRESHNESS` monitor without a lookback fires unpredictably. There is no skill that looks at a table's existing monitors and says "these are weak — here's the tightened version."
3. **Coverage suggestions are shallow.** `/bigeye-coverage` tells the user *which* dimensions are missing. It does not suggest *what* metric to create, with which parameters, grounded in the actual column profile.

This spec adds a **read-only intelligence layer** that addresses all three. No new write paths. No new mutation surfaces. Output is always rendered markdown the user copies or hands to `/bigeye-deploy` themselves.

Drivers:

1. **Reduce manual toil.** Vendor tickets drafted from a template + BigEye variables instead of blank slate.
2. **Raise monitor quality.** Surface weak monitors and concrete improvements.
3. **Make coverage recommendations actionable.** Pair missing dimensions with specific metric drafts the user can deploy in one step.

Not drivers:
- Automating vendor ticket submission (explicitly out of scope — plugin never creates tickets anywhere)
- Auto-applying monitor changes (explicitly out of scope — `/bigeye-deploy` remains the only write path)
- Source-warehouse integration (explicitly out of scope — heavy-mode SQL is rendered for the user to run manually)

---

## 2. Architecture overview

### 2.1 File layout after the rework

```
bigeye-plugin/
├── .claude-plugin/marketplace.json                (version bump 0.2.0 → 0.3.0)
├── README.md                                       (new rows + ticket-template note)
├── agents/bigeye-morning-report.md                 (unchanged)
├── skills/
│   ├── bigeye/
│   │   ├── SKILL.md                                (router: +2 intents, +2 ambiguous-menu rows)
│   │   └── references/
│   │       ├── conventions.md                      (unchanged)
│   │       ├── scope.md                            (+2 rows in Step F applicability table)
│   │       ├── cli.md                              (unchanged)
│   │       └── improve.md                          (NEW — shared substrate)
│   ├── bigeye-config/SKILL.md                      (unchanged)
│   ├── bigeye-triage/SKILL.md                      (Step 5: +1 next-action line)
│   ├── bigeye-rca/SKILL.md                         (unchanged)
│   ├── bigeye-coverage/SKILL.md                    (new Step 4b + new output section + new next-action)
│   ├── bigeye-deploy/SKILL.md                      (unchanged)
│   ├── bigeye-incidents/SKILL.md                   (unchanged)
│   ├── bigeye-ticket/
│   │   ├── SKILL.md                                (NEW)
│   │   └── templates/
│   │       └── default.md                          (NEW — shipped default template)
│   └── bigeye-improve/
│       └── SKILL.md                                (NEW)
└── docs/superpowers/
    ├── specs/2026-04-23-bigeye-intelligence-layer-design.md   (this spec)
    └── plans/                                                  (created by writing-plans next)
```

Per-user assets owned by the plugin:

```
~/.claude/bigeye-plugin/
├── profiles.json                                   (unchanged)
└── ticket-templates/                               (NEW — created on first /bigeye-ticket run)
    ├── default.md                                  (seeded from skills/bigeye-ticket/templates/default.md)
    └── <user-added>.md                             (added via wizard)
```

Only `/bigeye-ticket` writes to `ticket-templates/`. No other skill touches that directory.

### 2.2 Hard architectural rules (carried unchanged from the CLI-first spec)

1. **Read-only.** Neither new skill performs writes against BigEye. Both produce only markdown.
2. **CLI-first, MCP-optional.** Follow `cli.md` Step B for MCP detection; Step F for the degradation warning template. Neither skill hard-fails on MCP absence — they degrade per the rules in §5 of this spec.
3. **Scope applies.** `scope.md` Step F gets two new rows; both skills obey override flags (`--profile`, `--no-scope`, `--workspace`).

### 2.3 What changes in existing surfaces

- `/bigeye-coverage` gets a cheap weak-monitor scan step (CLI + data already in hand), a new output section, and a new next-action pointing to `/bigeye-improve`.
- `/bigeye-triage` gets one new next-action bullet suggesting `/bigeye-ticket <display_name>`.
- The `/bigeye` router learns two new intents.
- `scope.md` Step F gets two new rows.
- `README.md` gets two new command rows and a "Ticket templates" note.
- `marketplace.json` version bumps 0.2.0 → 0.3.0.

### 2.4 What does not change

- Slash command surface for existing skills (`/bigeye-config`, `/bigeye-triage`, `/bigeye-rca`, `/bigeye-coverage`, `/bigeye-deploy`, `/bigeye-incidents`)
- `profiles.json` schema
- Severity classification rules in `conventions.md`
- `cli.md` Step A/B/C/D/E/F/G routing and degradation rules
- Morning-report agent

---

## 3. `/bigeye-ticket` skill

### 3.1 Purpose

Render a markdown ticket draft from a BigEye issue using a user-supplied template. Output is copy-pasteable. No external system writes. Template storage is local per-user; a bundled default seeds first-run.

### 3.2 Arguments

Parse `$ARGUMENTS` left-to-right, removing scope flags (`--profile`, `--no-scope`, `--workspace`) first per `scope.md` Step B.

| Invocation | Behavior |
|---|---|
| `/bigeye-ticket <issue>` | Render `default` template for the named issue |
| `/bigeye-ticket --template <name> <issue>` | Use a specific named template |
| `/bigeye-ticket templates list` | Print name, modified-at, size for each template in `~/.claude/bigeye-plugin/ticket-templates/` |
| `/bigeye-ticket templates add <name>` | Wizard: paste template body, validate, save |
| `/bigeye-ticket templates edit <name>` | Wizard: re-paste body; preserve existing file until user confirms |
| `/bigeye-ticket templates delete <name>` | Confirm + remove file |
| `--internal-id` | Treat the numeric argument as an internal ID (bypass MCP display-name lookup) — required when MCP is unavailable |

Name validation (same pattern as profile names): `^[a-zA-Z0-9_-]+$`. Reject `default` for `add` unless the user explicitly confirms overwrite.

### 3.3 First-run seeding

When any `/bigeye-ticket <issue>` or `/bigeye-ticket --template <name> <issue>` invocation finds `~/.claude/bigeye-plugin/ticket-templates/` missing or empty:

1. Create the directory.
2. Copy the plugin-bundled `skills/bigeye-ticket/templates/default.md` to `~/.claude/bigeye-plugin/ticket-templates/default.md`.
3. Print one line: `Seeded default template. Run \`/bigeye-ticket templates edit default\` to customize, or \`/bigeye-ticket templates add <name>\` to add your own.`
4. Continue with the render (using `default` unless `--template <name>` names something else, in which case stop with the "template not found" error from §5).

### 3.4 Template format

- Plain markdown. Variable substitution uses Mustache-style `{{variable}}` placeholders — no nesting, no conditionals, no logic.
- Unknown placeholders (not in the catalog below) are left literal in the rendered output. The skill appends one line: `Warning: template referenced unknown variables: {{foo}}, {{bar}}`.
- No whitespace normalization — what the user writes is what renders.
- UTF-8 only.

### 3.5 Variable catalog

Authoritative in `skills/bigeye/references/improve.md`. Reproduced here:

| Variable | Source | MCP required? |
|---|---|---|
| `{{issue_display_name}}` | CLI issue JSON `displayName` | no |
| `{{issue_internal_id}}` | CLI issue JSON `id` | no |
| `{{status}}` | CLI issue JSON `status` mapped per `conventions.md` | no |
| `{{priority}}` | CLI issue JSON `priority` mapped per `conventions.md` | no |
| `{{dimension}}` | CLI issue JSON `dimensions[0]` | no |
| `{{metric_type}}` | `metricConfiguration.metricType` | no |
| `{{metric_name}}` | `metricConfiguration.name` | no |
| `{{table_name}}` | CLI issue JSON `tableName` | no |
| `{{schema_name}}` | CLI issue JSON `schemaName` | no |
| `{{column_name}}` | CLI issue JSON `columnName` or `—` | no |
| `{{data_source}}` | CLI issue JSON `warehouseName` | no |
| `{{opened_at}}` | CLI issue JSON `openedAt` (ISO-8601) | no |
| `{{time_since}}` | Computed from `openedAt` — human-readable ("2h ago") | no |
| `{{expected_value}}` | CLI issue JSON `events[0].expected` | no |
| `{{actual_value}}` | CLI issue JSON `events[0].actual` | no |
| `{{event_history}}` | Markdown bullet list rendered from `events[]` | no |
| `{{bigeye_url}}` | `https://app.bigeye.com/issue/{{issue_internal_id}}` | no |
| `{{sample_query}}` | Heuristic SQL skeleton based on metric type (see §3.6) | no |
| `{{downstream_tables}}` | MCP `get_issue_lineage_trace` → formatted as a bullet list of affected tables | **yes** |
| `{{related_issues}}` | MCP `list_related_issues` → formatted as a bullet list | **yes** |
| `{{resolution_steps}}` | MCP `get_resolution_steps` → numbered list | **yes** |

Deliberately **not** in the catalog: `{{severity}}`. The default template writes `Severity: Medium` as a literal value; users with severity-driven logic can reference `{{priority}}` in custom templates.

### 3.6 `{{sample_query}}` rendering rules

A minimal skeleton matched to the metric type. The plugin does NOT execute the query. Table shape is `{{schema_name}}.{{table_name}}`.

| Metric type | Rendered SQL |
|---|---|
| `FRESHNESS` (table-level) | `SELECT * FROM {{schema}}.{{table}} ORDER BY <timestamp_column> DESC LIMIT 100` (literal `<timestamp_column>` — user fills) |
| `PERCENT_NULL` | `SELECT * FROM {{schema}}.{{table}} WHERE {{column}} IS NULL LIMIT 100` |
| `COUNT_DISTINCT` | `SELECT {{column}}, COUNT(*) FROM {{schema}}.{{table}} GROUP BY 1 ORDER BY 2 DESC LIMIT 100` |
| `COUNT_ROWS` | `SELECT COUNT(*) FROM {{schema}}.{{table}}` |
| `VALID_REGEX` (or any regex-based) | `SELECT {{column}}, COUNT(*) FROM {{schema}}.{{table}} GROUP BY 1 ORDER BY 2 DESC LIMIT 50` |
| anything else | `-- no sample query available for metric type {{metric_type}}` (literal comment) |

### 3.7 MCP-absent behavior

For each MCP-only variable whose fetch fails (MCP unavailable or MCP call errors):

1. Substitute the placeholder with `_(unavailable — MCP not configured)_` (italicized parenthetical).
2. After rendering, append one footer line to stdout (below the rendered ticket fence):
   `Note: {{downstream_tables}}, {{related_issues}}, {{resolution_steps}} omitted — MCP not configured (see bigeye-mcp-install.md).`
   List only the variables that were actually affected.

Variables with `no` in the MCP column always render (CLI is sufficient).

### 3.8 Render-path procedure

- **Step 0** — Load scope + detect MCP per `scope.md` Steps A–E and `cli.md` Step B.
- **Step 1** — Resolve the issue. Same rules as `bigeye-rca` Step 1 (with `--internal-id` short-circuit; MCP `search_issues` otherwise; hard-fail with the standard pointer if both unavailable).
- **Step 2** — Fetch issue details via CLI `issues get-issues -iid <internal_id> -op $TMPDIR`.
- **Step 3** — If MCP available, fetch the three MCP-only payloads (lineage, related, resolution). Each call is best-effort; an individual failure degrades only that variable. Collect an "affected" list for the footer note.
- **Step 4** — Load the template file from `~/.claude/bigeye-plugin/ticket-templates/<name>.md`. On I/O error, follow §5 (`/bigeye-ticket` errors).
- **Step 5** — Substitute variables. Detect unknown placeholders (see §3.4) and buffer the warning line.
- **Step 6** — Emit output: a `Scope:` header per `scope.md` Step G, then the rendered ticket inside a triple-backtick fenced block so the user can copy cleanly, then the footer note (if any) and the unknown-variable warning (if any).
- **Step 7** — Print the standard chaining suggestion: `-> Run /bigeye-rca {{issue_display_name}} if you have not already investigated`.

### 3.9 Wizard flow for `templates add <name>` / `templates edit <name>`

Mirrors the `bigeye-config init` wizard's shape (one question at a time, summary before save).

1. Validate `<name>` against `^[a-zA-Z0-9_-]+$`. Reject `default` for `add` unless the user confirms overwrite.
2. If the file exists (both `add` and `edit`), read it and show the current size. For `add` on an existing file, ask: `A template named <name> already exists. Overwrite? (y/n)`.
3. Print a short form of the variable catalog (§3.5) so the user sees what they can reference.
4. Prompt: `Paste your template. Finish with a single line containing only EOF.`
5. Read lines until `EOF`. Cap at 200 lines of input; if no `EOF` after 200 lines, stop and ask the user to confirm intent or restart (see §5).
6. Show a preview: a line-count summary plus `Uses: {{table_name}}, {{dimension}}, ...` and `Unknown placeholders: none` (or a list).
7. Prompt: `Save? (y/n)`. On `n`, discard; do not touch disk. On `y`, write atomically (write to a temp file in the same dir, `fsync`, `rename`) to avoid partial writes.
8. Print: `Wrote ~/.claude/bigeye-plugin/ticket-templates/<name>.md.`

### 3.10 Default bundled template

Shipped verbatim at `skills/bigeye-ticket/templates/default.md`:

```
Service Request Name: BigEye #{{issue_display_name}} — {{dimension}} on {{table_name}}.{{column_name}}
Product Category: [Select appropriate category]
Sub-Category: [Select appropriate sub-category]
Domain: [URL of the domain if the SR refers to a specific one]
Fields / Attribute: {{column_name}}
Description:
{{dimension}} check failed on `{{schema_name}}.{{table_name}}` ({{data_source}}).
Metric: {{metric_type}} ({{metric_name}}).

Expected: {{expected_value}}
Actual: {{actual_value}}
First failing event: {{opened_at}} ({{time_since}})

Event history:
{{event_history}}

Downstream impact:
{{downstream_tables}}

Related issues:
{{related_issues}}

Suggested first-look query:
{{sample_query}}

Resolution guidance:
{{resolution_steps}}

Reference: BigEye issue #{{issue_display_name}} ({{bigeye_url}})

SR Type: Problem/Incident
Severity: Medium
```

The bracket placeholders (`[Select appropriate category]`, etc.) are intentionally not BigEye variables — they are fields the user fills manually when submitting the SR. The plugin does not touch them.

---

## 4. `/bigeye-improve` skill

### 4.1 Purpose

Analyze a table (or a single metric) and produce two kinds of recommendations:

1. **Weak existing monitors** — regex too permissive, lookback too short, thresholds too wide vs. recent distribution, missing schedule, or high false-positive rate.
2. **Missing coverage with concrete metric drafts** — grounded in BigEye's column profile when MCP is available, and in warehouse-sampled data when the user opts into heavy mode.

No writes. Output is markdown. Deploy is a separate user action via the unchanged `/bigeye-deploy`.

### 4.2 Arguments

Parse `$ARGUMENTS` left-to-right, removing scope flags first per `scope.md` Step B.

| Invocation | Behavior |
|---|---|
| `/bigeye-improve <table>` | Analyze all existing metrics + coverage on the table; heavy mode by default |
| `/bigeye-improve metric <metric_id>` | Single-metric deep analysis |
| `--light` | Skip the heavy-mode SQL loop; return config-only heuristics + MCP profile reads |
| `--sql-only` | Emit the heavy-mode SQL bundle, then stop (no paste-back second turn) |
| `--dimension <name>` | Limit coverage suggestions to one dimension (e.g., `freshness`, `validity`) |
| `--profile`, `--no-scope`, `--workspace` | Standard scope overrides |

`<table>` is either a bare name (matched within scope) or a fully-qualified `schema.table` / `source.schema.table`. When ambiguous, the skill asks which match the user meant.

### 4.3 Data sources by availability

| Data source | Access | Required? |
|---|---|---|
| Existing monitor config (regex, lookback, threshold, schedule) | CLI `catalog get-metric-info` or `metric get-info` | CLI |
| Issue history per monitor (false-positive rate) | CLI `issues get-issues` filtered by `tableName` | CLI |
| Column profile (null rate, distinct count, min/max, sample values) | MCP `get_table_profile` | Optional |
| Table-level dimension coverage + gaps | MCP `get_table_dimension_coverage` | Optional (required for coverage suggestions) |
| Column-level dimension coverage | MCP `get_column_dimension_coverage` | Optional |
| Deep distribution / regex match rate / top values | Heavy-mode SQL rendered by the skill; user runs it; pastes results | None (plugin never executes) |

### 4.4 Procedure

- **Step 0** — Load scope + detect MCP per `scope.md` + `cli.md`. Parse flags.
- **Step 1 — Existing monitors (always runs).**
  Enumerate metrics on the table via CLI. For each, score against the heuristics catalog in `improve.md` (§6.2 of this spec). Each hit produces a finding with severity (HIGH/MEDIUM/LOW per heuristic) and a concrete suggestion sentence.
- **Step 2 — Missing coverage (MCP-only).**
  If MCP available: call `get_table_dimension_coverage` and `get_column_dimension_coverage`; for each gap, draft a concrete metric spec (not applied — just rendered).
  If MCP unavailable: print the `cli.md` Step F warning with `{feature_name}=missing-coverage suggestions`; skip Step 2 only; continue with Steps 1, 4, 5, 6.
- **Step 3 — Profile-based refinement (MCP-only).**
  If MCP available: call `get_table_profile` for each column touched by Step 1 or 2. Refine suggestions: strict threshold when `null_rate=0.0`; switch `COUNT_DISTINCT` → `CATEGORICAL` when `distinct_count` is small; test proposed regex against sampled values from the profile.
  If MCP unavailable: skip; annotate affected rows with `(profile unavailable)`.
- **Step 4 — Emit the primary report.**
  Print the `Scope:` header (per `scope.md` Step G) followed by the `## Weak Monitors`, `## Coverage Suggestions`, and `## Deploy hints` sections from §4.6, derived from Steps 1–3. Omit any section that has zero rows.
- **Step 5 — Heavy-mode SQL bundle (default; skipped by `--light`).**
  Emit a SQL bundle for the columns that still need deeper reasoning after Steps 1–3. Bundle is rendered from templates in `improve.md` §6.3. Each query is preceded by a `-- query N: <purpose>` header.
  If `--sql-only`: emit the bundle, then stop — do not print the paste protocol.
  Otherwise: emit the bundle followed by the paste protocol from §4.5; end the current turn.
- **Step 6 — Refined recommendations (heavy mode only, triggered by the user's paste in a new turn).**
  Parse the user's pasted results per §4.5. Emit a second markdown block containing the `## Refined Recommendations` section and an updated `## Deploy hints` section reflecting any new or tightened suggestions discovered from the pasted data.
  On parse failure: report which `-- query N` blocks failed; ask for a re-paste of only those blocks; do not discard parsed blocks.

### 4.5 Heavy-mode paste protocol

After the SQL bundle, the skill prints exactly:

```
--- RUN THE QUERIES ABOVE AGAINST YOUR WAREHOUSE ---
--- THEN PASTE THE RESULTS BELOW AND SEND ---
--- BEGIN RESULTS ---
```

The user pastes results and sends a new message. The skill re-enters with the pasted text as its input.

Parse rules:
- Results are blocks separated by `-- query N` headers matching the headers the skill emitted.
- Each block expects a specific columnar shape (documented per-template in `improve.md` §6.3).
- Unparseable or missing block → ask for a re-paste of just that block. Do not discard parsed blocks.

If the user types `cancel` or a message that starts with `cancel`, produce the best-effort report from Steps 1–3 only, with a line noting that deep refinement was cancelled.

### 4.6 Output shape

Heavy mode emits **two markdown blocks across two turns**. `--light` and `--sql-only` emit a single block.

**First block (Step 4 output — printed in every mode):**

```
Scope: {per scope.md Step G}

## Monitor Improvement Report — {schema}.{table_name}

### Weak Monitors ({count})
| Metric ID | Column | Why | Suggested change |
|---|---|---|---|
| {id} | {col or "—"} | {heuristic reason} | {concrete suggestion} |

### Coverage Suggestions ({count})
| Column | Missing dimension | Suggested metric | Rationale |
|---|---|---|---|
| {col} | {dim} | {metric_type with parameters} | {profile-derived rationale or "config only"} |

### Deploy hints
- /bigeye-deploy columns {col} --metric-type {TYPE}
- /bigeye-deploy freshness
- ... one line per actionable suggestion
```

Followed in heavy / `--sql-only` modes by the SQL bundle (Step 5) and — heavy only — the paste protocol from §4.5.

**Second block (Step 6 output — heavy mode only, after paste):**

```
## Refined Recommendations
{Free-form markdown produced by reasoning over pasted SQL results.}

### Deploy hints (updated)
- /bigeye-deploy columns {col} --metric-type {TYPE}   ← refined threshold: {value}
- ... only rows added or changed relative to the first block's Deploy hints

-> Suggested next: run the highest-impact deploy hint, then `/bigeye-triage` in ~1 hour.
```

If a section has 0 rows, omit that section entirely (matching the triage convention). The final `-> Suggested next:` line is printed at the end of the *last* block emitted in the run (first block for `--light` / `--sql-only`, second block for heavy).

### 4.7 MCP-absent behavior (summary)

| Mode | MCP on | MCP off |
|---|---|---|
| `--light` | Weak monitors + coverage suggestions + profile refinement | Weak monitors only (config heuristics); coverage suggestions skipped with the standard warning |
| default (heavy) | Weak + coverage + profile + SQL bundle + refined recommendations | Weak + SQL bundle + refined recommendations (no coverage, no profile) |
| `--sql-only` | Weak + coverage + profile + SQL bundle (stops) | Weak + SQL bundle (stops) |

Hard-fail only when CLI itself cannot reach the workspace (auth or network failure). The standard CLI error text from `cli.md` Step G applies.

### 4.8 Scope application

- `<table>` argument is **always honored** — scope does not reject a user-named table (same rule as RCA's primary issue lookup).
- MCP calls that accept scope parameters receive them per `scope.md` Step E.
- No table-name input → fall back to the scope profile's `table_names`/`table_ids`. If empty or multiple, ask which to analyze. Never loop over all in-scope tables in a single heavy-mode run.

---

## 5. Edits to existing surfaces

### 5.1 `skills/bigeye-coverage/SKILL.md`

**New Step 4b** inserted between the current Step 4 (Prioritize Gaps) and Step 5 (Format Output):

> ### Step 4b: Cheap weak-monitor scan
>
> Using the data already fetched (monitor definitions from Step 1, issue history from Step 4), apply the "cheap" subset of the heuristics catalog in `improve.md` §6.2:
>
> - `REGEX_PERMISSIVE` — pattern in the known-weak set
> - `LOOKBACK_MISSING` — no lookback or `0 days`
> - `HIGH_FALSE_POSITIVE_RATE` — 3+ `FALSE_POSITIVE` closures in the last 30 days
> - `SCHEDULE_MISSING` — no schedule configured
>
> Collect findings into `improvable_count` and a list of `(metric_id, column, one-sentence reason)`.

**New output section** inserted before `### Suggested Monitor Deployment`, only when `improvable_count > 0`:

```
### Improvable Monitors ({improvable_count})
- Metric #{metric_id} on {column or "table-level"}: {one-sentence reason}
{... up to 5 lines}
{If > 5:}
... and {extra} more.
```

**New next-action line** appended to the existing next-action block (always printed on success, even when `improvable_count == 0`):

```
-> Run `/bigeye-improve {table_name}` for deep monitor recommendations (incl. weak-regex tightening, threshold tuning, distribution-aware suggestions)
```

No other changes. MCP-absent hard-fail behavior unchanged (the skill already hard-fails before Step 4b runs).

### 5.2 `skills/bigeye-triage/SKILL.md`

**One bullet added** to Step 5 (Suggest Next Actions), placed after the existing RCA/incidents suggestions:

```
- For any issue you want to hand to a data vendor: `/bigeye-ticket <display_name>`
```

No other changes.

### 5.3 `skills/bigeye/SKILL.md` (router)

Two rows added to the intent table:

| User intent | Invoke |
|---|---|
| "draft a ticket", "write a ticket for issue X", "vendor ticket", "SR" | Skill: `bigeye-ticket` with args passed through |
| "improve monitors", "tighten regex", "better thresholds", "recommend monitors", "weak monitors" | Skill: `bigeye-improve` with args passed through |

Two rows added to the "Ambiguous Intent" menu:

```
7. **Draft a vendor ticket** — render a markdown ticket for an issue (`/bigeye-ticket`)
8. **Improve monitors** — tighten weak monitors, recommend new ones (`/bigeye-improve`)
```

### 5.4 `skills/bigeye/references/scope.md`

Two rows added to the Step F per-skill applicability table:

| Skill | Apply scope to |
|---|---|
| `bigeye-ticket` | Primary issue lookup is **unscoped** (user named a specific issue). Scope applies only to MCP lineage/related calls for `{{downstream_tables}}` / `{{related_issues}}` |
| `bigeye-improve` | Table argument is unscoped when named explicitly. Scope applies to MCP profile/coverage calls if their schema accepts filters; no table-list enumeration (user always names one, or the profile resolves to a single in-scope table) |

### 5.5 `README.md`

Two rows added to the Commands table:

| `/bigeye-ticket [issue]` | Draft a copy-pasteable markdown vendor ticket |
| `/bigeye-improve [table]` | Deep recommendations for weak monitors and missing coverage |

One paragraph added under the **Configuration** section:

> **Ticket templates:** `/bigeye-ticket` reads and writes `~/.claude/bigeye-plugin/ticket-templates/<name>.md`. Seeded with a `default.md` on first run. Manage via `/bigeye-ticket templates add/edit/delete/list`.

### 5.6 `.claude-plugin/marketplace.json`

Version bumps from `"0.2.0"` to `"0.3.0"`. No other keys change.

---

## 6. Shared substrate: `skills/bigeye/references/improve.md`

New reference doc. Single source of truth for both new skills. Contents:

### 6.1 Template variable catalog

The table from §3.5, reproduced verbatim. Both `/bigeye-ticket` (renderer) and any future template consumer read the catalog from this file, not from their own SKILL.md.

### 6.2 Monitor-quality heuristics catalog

Each heuristic has:

- **ID** — stable string identifier, e.g. `REGEX_PERMISSIVE`
- **Severity** — HIGH / MEDIUM / LOW (static per heuristic)
- **Cheap?** — boolean; `true` means `/bigeye-coverage` Step 4b can run it without extra data fetches
- **Detection rule** — pseudocode against the CLI monitor JSON + issue history
- **Suggestion template** — parameterized sentence

Initial heuristics:

| ID | Severity | Cheap? | Detection | Suggestion template |
|---|---|---|---|---|
| `REGEX_PERMISSIVE` | HIGH | yes | Metric is a regex-based metric AND its pattern is in `{".+", ".*", ".+@.+", "[A-Za-z0-9]+"}` | Tighten regex — current pattern `{pattern}` matches too broadly. Propose `{tightened}` (derived in Step 3/5 or left as "needs heavy-mode data") |
| `LOOKBACK_MISSING` | HIGH | yes | `lookback` absent OR `lookback_window == 0` | Set `lookback_window` to at least 1 day (`DATA_TIME`) |
| `SCHEDULE_MISSING` | MEDIUM | yes | `schedule` absent | Add a schedule matching the table's refresh cadence |
| `HIGH_FALSE_POSITIVE_RATE` | MEDIUM | yes | 3+ closures with `FALSE_POSITIVE` label in the last 30 days for this metric | Review monitor parameters — high FP rate suggests thresholds too tight or wrong metric type |
| `THRESHOLD_DEFAULT` | LOW | no | Threshold equals the Bigeye system default for its metric type (requires Step 3 profile comparison to know) | Tune threshold against observed distribution (see Refined Recommendations) |
| `METRIC_TYPE_MISMATCH` | MEDIUM | no | Heavy-mode finds low distinct count on a `COUNT_DISTINCT` metric (< 10) | Switch to `CATEGORICAL` distribution monitor |

The "Cheap?" column gates which heuristics `/bigeye-coverage` Step 4b runs. Both skills share the same suggestion templates.

### 6.3 Heavy-mode SQL templates

One SQL skeleton per investigation type, parameterized by `{schema}`, `{table}`, `{column}`, and optional `{pattern}`. Expected result shape is documented alongside each template so §4.5 parsing is deterministic.

| Template ID | Purpose | SQL skeleton | Expected result columns |
|---|---|---|---|
| `NULL_DISTINCT` | Baseline null rate + distinct count | `SELECT COUNT(*) AS total, COUNT({column}) AS non_null, COUNT(DISTINCT {column}) AS distinct_values FROM {schema}.{table}` | `total`, `non_null`, `distinct_values` |
| `REGEX_MATCH` | Regex match rate vs. current or candidate pattern | `SELECT SUM(CASE WHEN {column} REGEXP '{pattern}' THEN 1 ELSE 0 END) AS matches, COUNT({column}) AS non_null FROM {schema}.{table}` | `matches`, `non_null` |
| `TOP_VALUES` | 20 most common values (regex candidate derivation) | `SELECT {column}, COUNT(*) AS n FROM {schema}.{table} GROUP BY 1 ORDER BY 2 DESC LIMIT 20` | `{column}`, `n` |
| `DISTRIBUTION_BUCKETS` | 10 equal-width buckets for numeric columns | Dialect-specific (Snowflake `WIDTH_BUCKET`, BigQuery `APPROX_QUANTILES` fallback). Implementation resolves via CLI-detected `warehouseName` dialect | bucket boundaries + counts |
| `DAILY_NULL_RATE` | Null rate trend over last 30 days | `SELECT DATE({timestamp_column}) AS d, COUNT(*) AS total, COUNT({column}) AS non_null FROM {schema}.{table} WHERE {timestamp_column} >= CURRENT_DATE - INTERVAL '30' DAY GROUP BY 1 ORDER BY 1` | `d`, `total`, `non_null` |

The `DISTRIBUTION_BUCKETS` template is dialect-sensitive. The implementation must look up the warehouse dialect from the CLI's `warehouseName` → warehouse-type mapping (part of the table metadata the CLI returns) and emit the correct SQL. If the dialect is unknown, emit a comment-only placeholder: `-- distribution buckets: unsupported for warehouse type {type} — skip`.

### 6.4 Paste-parsing protocol

The delimiter rules from §4.5, plus column-name expectations per template (from §6.3). Documents the re-paste recovery flow (§4.5).

### 6.5 Default severity fallback

Documented here: `{{severity}}` is deliberately absent from the catalog. `default.md` uses literal `Severity: Medium`. Custom templates may reference `{{priority}}` if they want BigEye-priority-driven severity.

---

## 7. Error handling

### 7.1 `/bigeye-ticket`

| Condition | Behavior |
|---|---|
| Issue not found (CLI or MCP) | Print the CLI/MCP error; suggest re-checking the display name; stop |
| Template file not found | List templates available in `~/.claude/bigeye-plugin/ticket-templates/`; suggest `/bigeye-ticket templates add <name>`; stop |
| Template file I/O error (permissions, encoding) | Print the OS error + file path; do not delete the file; stop |
| Unknown `{{variable}}` in template | Leave placeholder literal; append one warning line listing unknowns; continue |
| MCP-only variable requested, MCP down | Substitute `_(unavailable — MCP not configured)_`; append the footer note listing affected variables |
| Wizard: paste exceeds 200 lines without `EOF` | Stop reading; ask the user to confirm intent or restart; do not write anything |
| Wizard: confirm `n` | Discard in-memory template; do not touch disk |

### 7.2 `/bigeye-improve`

| Condition | Behavior |
|---|---|
| Table not found | Print `bigeye catalog get-table-info` error verbatim; suggest `/bigeye-config show` to verify scope; stop |
| No metrics on table AND no MCP | Print `Nothing to improve — no existing monitors and MCP unavailable, so no coverage data. See bigeye-mcp-install.md.`; exit cleanly |
| MCP profile fetch partial failure | Continue with the successful columns; mark failed-column rows `(profile unavailable for this column)` |
| Heavy-mode paste parse failure | Report which `-- query N` blocks failed; ask for re-paste of only those blocks; do not reset progress |
| User sends `cancel` mid heavy-mode | Produce best-effort report from Steps 1–3; note that deep refinement was cancelled |
| Warehouse dialect unknown for `DISTRIBUTION_BUCKETS` | Emit the comment-only placeholder from §6.3; continue with remaining templates |

### 7.3 Shared rules

Both skills follow `cli.md` Step F for the MCP-absent warning template (no new warning text is invented in this spec). Both skills follow `cli.md` Step G for CLI error handling.

---

## 8. Verification (manual)

No automated tests — matches the existing plugin convention. The following checks must pass on a real workspace before merging.

### 8.1 `/bigeye-ticket`

1. First run with no `~/.claude/bigeye-plugin/ticket-templates/` directory seeds `default.md` and renders successfully.
2. `templates add monday` round-trip: add → `templates list` shows it → render with `--template monday <issue>` → `templates edit monday` preserves → `templates delete monday` removes cleanly.
3. Render against a known issue with MCP on — all variables in §3.5 populate.
4. Render against a known issue with MCP off — MCP-only variables show `_(unavailable — MCP not configured)_` and the footer note appears.
5. Render with `--template nonexistent` → error path from §7.1; lists available templates.
6. Render with a template containing `{{nonsense}}` → placeholder preserved literal; warning line printed.
7. `--internal-id 12345` path works with MCP off.
8. Wizard: sending > 200 lines without `EOF` triggers the overflow prompt and does not write.

### 8.2 `/bigeye-improve`

1. `/bigeye-improve <table> --light` with MCP off — produces weak-monitors section only (config-heuristic subset).
2. `/bigeye-improve <table> --light` with MCP on — adds coverage suggestions and profile-refined rows.
3. `/bigeye-improve <table>` default (heavy) — emits the SQL bundle + paste delimiter.
4. Second turn (paste) — Refined Recommendations section appears; parsed rows reflect pasted data.
5. `/bigeye-improve metric <id>` — single-metric analysis path produces a one-row Weak Monitors report.
6. `--sql-only` — prints SQL and exits without the paste delimiter.
7. MCP off AND no metrics on the table — clean exit line from §7.2.
8. Heavy-mode paste with one block corrupted — only that block fails; skill asks for re-paste of that block; other blocks remain parsed.
9. User sends `cancel` at paste step — best-effort report produced; cancellation note appears.

### 8.3 `/bigeye-coverage` (regression + additions)

1. Existing behavior unchanged for profiles with MCP on (regression).
2. New "Improvable Monitors" section appears when at least one cheap heuristic hits.
3. New "Run `/bigeye-improve <table>`" next-action line appears on every successful run.

### 8.4 `/bigeye-triage`

1. Step 5 output includes "For any issue you want to hand to a data vendor: `/bigeye-ticket <display_name>`".

### 8.5 Router

1. `/bigeye draft a ticket for 10921` → routes to `/bigeye-ticket 10921`.
2. `/bigeye improve orders table` → routes to `/bigeye-improve orders`.
3. `/bigeye what's broken` still routes to `/bigeye-triage` (regression).

### 8.6 Version + README

1. `marketplace.json` reads `"version": "0.3.0"`.
2. README Commands table lists the two new skills; Configuration section includes the ticket-templates note.

---

## 9. Out of scope

- Automating vendor ticket submission (Atlassian / Monday / other MCPs will not be invoked by this plugin release).
- Any write to BigEye (`metric upsert`, `issues update-issue`, `create_incident`) beyond what `/bigeye-deploy` and `/bigeye-incidents` already do today.
- Source-warehouse integration (heavy-mode SQL is rendered, never executed).
- Multi-table analysis in a single `/bigeye-improve` run.
- Template sharing / import-export (out of scope; users can copy files in the template directory manually if they want).
- Auto-refreshing suggestions on a schedule (no cron / agent changes in this spec).
- Severity auto-mapping in the default template (user chose literal `Medium`).

---

## 10. Open questions

None at design-approval time. All design decisions listed here were confirmed during brainstorming on 2026-04-23.
