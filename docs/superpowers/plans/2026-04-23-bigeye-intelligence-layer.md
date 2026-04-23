# BigEye Plugin — Intelligence Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only intelligence layer to the BigEye plugin: two new skills (`/bigeye-ticket` for markdown ticket drafts; `/bigeye-improve` for weak-monitor analysis and coverage recommendations), surgical edits to three existing skills (`/bigeye-coverage`, `/bigeye-triage`, the `/bigeye` router), a new shared reference doc, a bundled default ticket template, and a 0.2.0 → 0.3.0 version bump.

**Architecture:** One new shared reference (`skills/bigeye/references/improve.md`) holds the template variable catalog, monitor-quality heuristics, heavy-mode SQL templates, and paste-parsing protocol that both new skills consume. `/bigeye-ticket` renders markdown from user-authored templates stored at `~/.claude/bigeye-plugin/ticket-templates/<name>.md`, seeded on first run from a bundled `default.md`. `/bigeye-improve` combines CLI monitor metadata, MCP profile data, and an optional user-mediated SQL loop (plugin emits SQL → user runs it → user pastes results → plugin refines) to surface weak existing monitors and draft new monitor specs. Coverage and triage gain one-line pointers to the new skills. No new write paths.

**Tech Stack:** Markdown skill files, JSON/INI config already in place, Bash invocations of `bigeye-cli`. No source code, no test framework. Each task's verification is either (a) confirming file content via `Read` / `Grep`, or (b) a manual scenario at the end (Task 11).

**Spec reference:** `docs/superpowers/specs/2026-04-23-bigeye-intelligence-layer-design.md`

**Commit policy:** Every task ends with a `git add` step ("Stage"). Plan tasks NEVER run `git commit` — the user owns all commits. Batching multiple tasks into one commit is the user's choice.

---

## File Structure

**New files:**
- `skills/bigeye/references/improve.md` — shared reference (variable catalog + heuristics + SQL templates + paste protocol) — Task 1
- `skills/bigeye-ticket/templates/default.md` — bundled default template shipped in the plugin — Task 2
- `skills/bigeye-ticket/SKILL.md` — ticket-drafting skill — Task 3
- `skills/bigeye-improve/SKILL.md` — monitor-improvement skill — Task 4

**Modified files:**
- `skills/bigeye-coverage/SKILL.md` — insert Step 4b (cheap weak-monitor scan), new output section, new next-action — Task 5
- `skills/bigeye-triage/SKILL.md` — one bullet in Step 5 — Task 6
- `skills/bigeye/SKILL.md` — 2 rows in router intent table + 2 rows in ambiguous-intent menu — Task 7
- `skills/bigeye/references/scope.md` — 2 rows in Step F applicability table — Task 8
- `README.md` — 2 rows in commands table + ticket-templates note — Task 9
- `.claude-plugin/marketplace.json` — version 0.2.0 → 0.3.0 — Task 10
- `pyproject.toml` — version 0.2.0 → 0.3.0 — Task 10

**No automated test files** — validation is manual per spec §8. Task 11 is the checklist.

**Order rationale:** `improve.md` first (Task 1) because every later skill references it. Default template next (Task 2) because `/bigeye-ticket` bundles it. Then the two new skills (Tasks 3–4). Then the three small existing-skill edits (Tasks 5–7). Then the two reference edits (Tasks 8–9 — scope and README). Then version bumps (Task 10). Manual validation last (Task 11).

---

## Task 1: Create the `improve.md` shared reference

**Files:**
- Create: `skills/bigeye/references/improve.md`

- [ ] **Step 1: Write the new reference file**

Write `skills/bigeye/references/improve.md` with exactly this content:

````markdown
# BigEye Plugin — Intelligence Layer Reference

Shared substrate for `bigeye-ticket` and `bigeye-improve`. Skills that render `{{variable}}` placeholders, scan monitors for quality issues, or emit heavy-mode SQL read from this doc rather than defining rules inline.

Sections:
- §1 — Template variable catalog
- §2 — Monitor-quality heuristics
- §3 — Heavy-mode SQL templates
- §4 — Paste-parsing protocol
- §5 — Default severity fallback

---

## §1. Template variable catalog

Used by `bigeye-ticket`. All variables are substituted in a single pass using Mustache-style `{{name}}` placeholders. Unknown placeholders are left literal in the output with a one-line warning appended.

| Variable | Source | MCP required? |
|---|---|---|
| `{{issue_display_name}}` | CLI issue JSON `displayName` | no |
| `{{issue_internal_id}}` | CLI issue JSON `id` | no |
| `{{status}}` | CLI issue JSON `status` mapped per `conventions.md` Status Display Mapping | no |
| `{{priority}}` | CLI issue JSON `priority` mapped per `conventions.md` Priority Mapping | no |
| `{{dimension}}` | CLI issue JSON `dimensions[0]` (first item) | no |
| `{{metric_type}}` | `metricConfiguration.metricType` | no |
| `{{metric_name}}` | `metricConfiguration.name` | no |
| `{{table_name}}` | CLI issue JSON `tableName` | no |
| `{{schema_name}}` | CLI issue JSON `schemaName` | no |
| `{{column_name}}` | CLI issue JSON `columnName` or `—` if table-level | no |
| `{{data_source}}` | CLI issue JSON `warehouseName` | no |
| `{{opened_at}}` | CLI issue JSON `openedAt` (ISO-8601) | no |
| `{{time_since}}` | Computed from `openedAt` — human-readable ("2h ago", "3d ago") | no |
| `{{expected_value}}` | CLI issue JSON `events[0].expected` | no |
| `{{actual_value}}` | CLI issue JSON `events[0].actual` | no |
| `{{event_history}}` | Markdown bullet list rendered from `events[]` (one bullet per event: `- {timestamp} — {metric_value}`) | no |
| `{{bigeye_url}}` | `https://app.bigeye.com/issue/{{issue_internal_id}}` | no |
| `{{sample_query}}` | Heuristic SQL skeleton based on metric type (§1.1) | no |
| `{{downstream_tables}}` | MCP `get_issue_lineage_trace` → formatted bullet list of affected tables | **yes** |
| `{{related_issues}}` | MCP `list_related_issues` → formatted bullet list | **yes** |
| `{{resolution_steps}}` | MCP `get_resolution_steps` → numbered list | **yes** |

Deliberately **not** in the catalog: `{{severity}}`. See §5.

### §1.1 `{{sample_query}}` rendering rules

Matched to the metric type. The plugin never executes the query. Table shape is `{{schema_name}}.{{table_name}}`.

| Metric type | Rendered SQL |
|---|---|
| `FRESHNESS` (table-level) | `SELECT * FROM {schema}.{table} ORDER BY <timestamp_column> DESC LIMIT 100` (literal `<timestamp_column>` — user fills) |
| `PERCENT_NULL` | `SELECT * FROM {schema}.{table} WHERE {column} IS NULL LIMIT 100` |
| `COUNT_DISTINCT` | `SELECT {column}, COUNT(*) FROM {schema}.{table} GROUP BY 1 ORDER BY 2 DESC LIMIT 100` |
| `COUNT_ROWS` | `SELECT COUNT(*) FROM {schema}.{table}` |
| `VALID_REGEX` (or any regex-based metric) | `SELECT {column}, COUNT(*) FROM {schema}.{table} GROUP BY 1 ORDER BY 2 DESC LIMIT 50` |
| anything else | `-- no sample query available for metric type {metric_type}` (literal comment) |

### §1.2 MCP-absent substitution

When an MCP-only variable cannot be populated (MCP unavailable or an individual MCP call errored):

1. Substitute the placeholder with `_(unavailable — MCP not configured)_` (italic parenthetical).
2. After rendering the template body, append one footer line (below the rendered fence) listing the affected variables:
   `Note: {{downstream_tables}}, {{related_issues}}, {{resolution_steps}} omitted — MCP not configured (see bigeye-mcp-install.md).`
   Include only variables that were actually affected.

---

## §2. Monitor-quality heuristics

Used by both `bigeye-improve` (full scan) and `bigeye-coverage` (cheap subset in Step 4b). Each heuristic has:

- **ID** — stable identifier
- **Severity** — HIGH / MEDIUM / LOW (static per heuristic)
- **Cheap?** — `yes` means `bigeye-coverage` Step 4b can run it with data already in hand; `no` requires extra fetches or profile data that only `bigeye-improve` gathers
- **Detection rule** — pseudocode against CLI monitor JSON + issue history
- **Suggestion template** — parameterized sentence used in the output row

| ID | Severity | Cheap? | Detection | Suggestion template |
|---|---|---|---|---|
| `REGEX_PERMISSIVE` | HIGH | yes | Metric is a regex-based metric AND its pattern is in the known-weak set `{".+", ".*", ".+@.+", "[A-Za-z0-9]+"}` | Tighten regex — current pattern `{pattern}` matches too broadly. Propose `{tightened}` (from §3/§4 data; otherwise the literal text `needs heavy-mode data`) |
| `LOOKBACK_MISSING` | HIGH | yes | `lookback` field absent OR `lookback_window == 0` | Set `lookback_window` to at least 1 day (`DATA_TIME`) |
| `SCHEDULE_MISSING` | MEDIUM | yes | `schedule` field absent | Add a schedule matching the table's refresh cadence |
| `HIGH_FALSE_POSITIVE_RATE` | MEDIUM | yes | 3+ closures with `FALSE_POSITIVE` label in the last 30 days for this metric | Review monitor parameters — high FP rate suggests thresholds too tight or wrong metric type |
| `THRESHOLD_DEFAULT` | LOW | no | Threshold equals the Bigeye system default for its metric type (requires profile comparison to know) | Tune threshold against observed distribution (see Refined Recommendations) |
| `METRIC_TYPE_MISMATCH` | MEDIUM | no | Heavy-mode finds `distinct_count < 10` on a `COUNT_DISTINCT` metric | Switch to `CATEGORICAL` distribution monitor |

The "Cheap?" column gates which heuristics `bigeye-coverage` Step 4b runs. Both skills share the same suggestion templates.

---

## §3. Heavy-mode SQL templates

Used by `bigeye-improve` Step 5. Each template has a `-- query N: <purpose>` header in the emitted bundle. Result columns are documented per template so §4 paste-parsing is deterministic.

All templates are rendered in the dialect of the source warehouse. `bigeye-improve` looks up the warehouse type from the CLI's `catalog get-table-info` output (the `warehouseType` field, e.g. `SNOWFLAKE`, `BIGQUERY`, `REDSHIFT`, `POSTGRES`). Where a template differs by dialect, the renderer picks the correct form; if the dialect is unknown, the renderer emits a comment-only placeholder (`-- query N: unsupported for warehouse type {type} — skip`) and continues with the next template.

| Template ID | Purpose | SQL skeleton (Snowflake/Postgres-like; dialect-adjusted at render time) | Expected result columns |
|---|---|---|---|
| `NULL_DISTINCT` | Baseline null rate + distinct count | `SELECT COUNT(*) AS total, COUNT({column}) AS non_null, COUNT(DISTINCT {column}) AS distinct_values FROM {schema}.{table}` | `total`, `non_null`, `distinct_values` |
| `REGEX_MATCH` | Match rate against a current or candidate pattern | `SELECT SUM(CASE WHEN REGEXP_LIKE({column}, '{pattern}') THEN 1 ELSE 0 END) AS matches, COUNT({column}) AS non_null FROM {schema}.{table}` (Snowflake `REGEXP_LIKE`; Postgres `{column} ~ '{pattern}'`; BigQuery `REGEXP_CONTAINS`) | `matches`, `non_null` |
| `TOP_VALUES` | 20 most common values (for regex candidate derivation) | `SELECT {column}, COUNT(*) AS n FROM {schema}.{table} GROUP BY 1 ORDER BY 2 DESC LIMIT 20` | `{column}`, `n` |
| `DISTRIBUTION_BUCKETS` | 10 equal-width buckets for numeric columns | Dialect-specific. Snowflake/Postgres: `WIDTH_BUCKET`. BigQuery: `APPROX_QUANTILES` fallback. Redshift: `WIDTH_BUCKET`. Unknown dialect: emit the skip placeholder | bucket boundaries + counts |
| `DAILY_NULL_RATE` | Null-rate trend over 30 days | `SELECT DATE({timestamp_column}) AS d, COUNT(*) AS total, COUNT({column}) AS non_null FROM {schema}.{table} WHERE {timestamp_column} >= CURRENT_DATE - INTERVAL '30' DAY GROUP BY 1 ORDER BY 1` (literal `{timestamp_column}` — user fills) | `d`, `total`, `non_null` |

The renderer only includes templates whose columns need the data. Example: if all columns touched by Steps 1–3 are already fully characterised, no bundle is emitted and the skill skips Steps 5–6.

---

## §4. Paste-parsing protocol

Used by `bigeye-improve` to consume heavy-mode query results across a turn boundary.

### §4.1 Emission

After the SQL bundle (§3), emit exactly:

```
--- RUN THE QUERIES ABOVE AGAINST YOUR WAREHOUSE ---
--- THEN PASTE THE RESULTS BELOW AND SEND ---
--- BEGIN RESULTS ---
```

End the current turn after this block. The user will paste results and send a new message.

### §4.2 Parsing

- The user's next message is expected to contain one section per emitted `-- query N: <purpose>` header. Sections may appear in any order.
- For each section, extract the tabular rows and match against the expected result columns from §3.
- Unparseable or missing sections → ask for a re-paste of only those sections. Preserve sections that parsed successfully.

### §4.3 Cancellation

If the user's next message starts with `cancel` (case-insensitive), produce a best-effort report from Steps 1–3 only, and append one line:
`Deep refinement cancelled — Refined Recommendations section omitted.`

---

## §5. Default severity fallback

`{{severity}}` is **not** a template variable. The bundled default template at `skills/bigeye-ticket/templates/default.md` writes `Severity: Medium` as a literal value. Custom templates that want BigEye-priority-driven severity can reference `{{priority}}` from §1 instead.
````

- [ ] **Step 2: Verify file content**

Use the `Read` tool on `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/improve.md`. Confirm:
- First line is `# BigEye Plugin — Intelligence Layer Reference`
- `## §1. Template variable catalog` appears
- `## §2. Monitor-quality heuristics` appears
- `## §3. Heavy-mode SQL templates` appears
- `## §4. Paste-parsing protocol` appears
- `## §5. Default severity fallback` appears
- The `{{severity}}` line in §5 says *not* a template variable

- [ ] **Step 3: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye/references/improve.md
```

---

## Task 2: Create the bundled default ticket template

**Files:**
- Create: `skills/bigeye-ticket/templates/default.md`

- [ ] **Step 1: Create the templates directory and write the default file**

The directory `skills/bigeye-ticket/templates/` does not exist yet. Use the `Write` tool — it will create the parent directory automatically.

Write `skills/bigeye-ticket/templates/default.md` with exactly this content (note: the file intentionally contains no frontmatter — it is a template, not a skill):

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

- [ ] **Step 2: Verify file content**

Use the `Read` tool on `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-ticket/templates/default.md`. Confirm:
- Line 1 starts with `Service Request Name: BigEye #{{issue_display_name}}`
- Last line is `Severity: Medium`
- `{{severity}}` does NOT appear anywhere in the file

Use `Grep` with pattern `\{\{severity\}\}` on this file; expect zero matches.

- [ ] **Step 3: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye-ticket/templates/default.md
```

---

## Task 3: Create `skills/bigeye-ticket/SKILL.md`

**Files:**
- Create: `skills/bigeye-ticket/SKILL.md`

- [ ] **Step 1: Write the new skill file**

Write `skills/bigeye-ticket/SKILL.md` with exactly this content:

````markdown
---
name: bigeye-ticket
description: Use when the user wants to draft a vendor ticket, write a Service Request, or generate a markdown report for a data vendor about a BigEye issue. Render-only — no external ticketing system writes.
user-invocable: true
---

# BigEye Ticket Drafter

Renders a markdown ticket draft from a BigEye issue using a user-authored template. Output is copy-pasteable markdown. The plugin never submits tickets anywhere.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for status/priority mapping, `skills/bigeye/references/scope.md` for scope loading, `skills/bigeye/references/cli.md` for CLI invocation and MCP-availability detection, and `skills/bigeye/references/improve.md` §1 for the template variable catalog.

## Arguments

Parse `$ARGUMENTS`. Remove `--profile`, `--no-scope`, `--workspace` scope flags first per `scope.md` Step B.

| Invocation | Behavior |
|---|---|
| `/bigeye-ticket <issue>` | Render `default` template for the named issue |
| `/bigeye-ticket --template <name> <issue>` | Use a specific named template |
| `/bigeye-ticket templates list` | Print name, modified-at, size for each template in `~/.claude/bigeye-plugin/ticket-templates/` |
| `/bigeye-ticket templates add <name>` | Wizard: paste template body, validate, save |
| `/bigeye-ticket templates edit <name>` | Wizard: re-paste body; preserve existing file until user confirms |
| `/bigeye-ticket templates delete <name>` | Confirm + remove file |
| `--internal-id` | Treat the numeric argument as an internal ID (bypass MCP display-name lookup) — required when MCP is unavailable |

Template-name validation: `^[a-zA-Z0-9_-]+$`. Reject `default` for `add` unless the user explicitly confirms overwrite.

## Render Path

### Step 0: Load scope and detect MCP

Follow `scope.md` Steps A–E then `cli.md` Step B. Per `scope.md` Step F, the primary issue lookup is **unscoped** — scope applies only to MCP lineage/related calls.

### Step 1: Seed templates directory on first run

If `~/.claude/bigeye-plugin/ticket-templates/` is missing or empty:

1. Create the directory.
2. Copy the bundled template from the plugin directory to `~/.claude/bigeye-plugin/ticket-templates/default.md`. The bundled file is at `skills/bigeye-ticket/templates/default.md` inside the plugin checkout.
3. Print exactly one line:
   `Seeded default template. Run /bigeye-ticket templates edit default to customize, or /bigeye-ticket templates add <name> to add your own.`
4. Continue with the render. If `--template <name>` names something other than `default`, stop with the "template not found" error in §Errors.

### Step 2: Resolve the issue

Parse the argument:
- If `--internal-id` was provided, treat the number as an internal ID directly; set `internal_id={number}`. Skip the MCP lookup.
- Otherwise the number is a display name; must be resolved via MCP.

**Display-name → internal-ID lookup (MCP required):**

If `MCP_AVAILABLE=true`:
  Call `mcp__bigeye__search_issues` with `name_query: "{number}"`. If no match, tell the user and stop. If multiple, list and ask which. Extract `id` (internal ID).

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=display-name lookup` and `{CLI-only workaround}=Re-run with --internal-id <internal-id> (find the internal ID in the Bigeye UI URL: app.bigeye.com/issue/<internal-id>)`. Stop the skill.

### Step 3: Fetch issue details via CLI

Use CLI per `cli.md` Step C:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> issues get-issues -iid <internal_id> -op "$TMPDIR"
```

Read the single JSON file. Extract all CLI-sourced variables per `improve.md` §1 (the rows with `MCP required? = no`).

### Step 4: Fetch MCP-only variables (best-effort)

Track an `affected_vars` list. For each MCP-only variable:

- `{{downstream_tables}}` — if `MCP_AVAILABLE=true`, call `mcp__bigeye__get_issue_lineage_trace` with `issue_id: {internal_id}`, `include_impact_analysis: true`, `max_depth: 3`. Format the downstream nodes as a bullet list. On error or MCP unavailable: substitute `_(unavailable — MCP not configured)_` and add `{{downstream_tables}}` to `affected_vars`.
- `{{related_issues}}` — if `MCP_AVAILABLE=true`, call `mcp__bigeye__list_related_issues` with `starting_issue_id: {internal_id}`. Format as bullet list. On error or MCP unavailable: substitute and add to `affected_vars`.
- `{{resolution_steps}}` — if `MCP_AVAILABLE=true`, call `mcp__bigeye__get_resolution_steps` with `issue_id: {internal_id}`. Format as numbered list. On error or MCP unavailable: substitute and add to `affected_vars`.

Apply `scope.md` Step E filtering to the MCP calls (scope affects which downstream/related items are kept; the primary issue itself is unscoped per Step 0).

### Step 5: Render `{{sample_query}}`

Pick the skeleton from `improve.md` §1.1 based on `{{metric_type}}`. Substitute `{schema}`, `{table}`, `{column}` with the issue's values. If the metric type doesn't match a row, render the literal comment `-- no sample query available for metric type {{metric_type}}`.

### Step 6: Load the template file

Template file path: `~/.claude/bigeye-plugin/ticket-templates/<name>.md` (`<name>` defaults to `default` if `--template` not given).

On I/O error (file missing, permission denied, invalid UTF-8): follow §Errors.

### Step 7: Substitute variables

Single-pass replacement of every `{{variable}}` occurrence. Variables in `improve.md` §1 substitute with their resolved values. Any `{{...}}` not in the catalog is left literal; collect the unknowns into an `unknown_vars` list for the warning line.

### Step 8: Emit output

Print in this exact order:

1. `Scope: {per scope.md Step G}`
2. Blank line.
3. A triple-backtick fenced block containing the rendered ticket body. The fence opens with three backticks on their own line and closes with three backticks on their own line.
4. Blank line.
5. If `affected_vars` is non-empty: one line — `Note: {comma-separated {{variable}} names from affected_vars} omitted — MCP not configured (see bigeye-mcp-install.md).`
6. If `unknown_vars` is non-empty: one line — `Warning: template referenced unknown variables: {comma-separated {{variable}} names}`.
7. Blank line.
8. Suggested next: `-> Run /bigeye-rca {{issue_display_name}} if you have not already investigated.`

## Wizard Flow (`templates add <name>` / `templates edit <name>`)

Ask one question at a time. Mirror the `bigeye-config init` pattern.

1. Validate `<name>` against `^[a-zA-Z0-9_-]+$`. Reject invalid names with: `Template name must match ^[a-zA-Z0-9_-]+$.`
2. For `add` with `<name>=default`, ask: `The bundled default template already exists. Overwrite it? (y/n)` — on `n`, stop.
3. If the file exists (both modes): `A template named <name> already exists (size={size} bytes). {For edit: show current size.} {For add: ask Overwrite? (y/n)} — on n, stop.`
4. Print a short form of the variable catalog — one line per variable, grouped "CLI-sourced" vs "MCP-only", referencing `improve.md` §1 for the full list.
5. Prompt: `Paste your template. Finish with a single line containing only EOF.`
6. Read lines until `EOF`. Cap at 200 lines of body. If no `EOF` after 200 lines, stop and ask: `Paste exceeded 200 lines without EOF terminator. Restart the wizard? (y/n)` — on `n`, exit without writing.
7. Compute a usage summary by scanning the pasted body for `{{...}}` occurrences. Categorise each into "used" (in `improve.md` §1) or "unknown". Print: `Uses: {comma-separated used}. Unknown placeholders: {comma-separated unknown, or "none"}.`
8. Prompt: `Save? (y/n)` — on `n`, discard without writing.
9. On `y`, write atomically: write to a sibling temp file in the same directory, then rename over the target. This avoids partial writes if the tool is interrupted.
10. Print: `Wrote ~/.claude/bigeye-plugin/ticket-templates/<name>.md.`

### `templates list`

Read the directory. For each `*.md` file, print one row:
```
| Template | Modified | Size |
|---|---|---|
| {name} | {ISO-8601 mtime} | {bytes} |
```

If the directory is missing or empty: print `No templates yet. Run /bigeye-ticket <issue> to seed the default, or /bigeye-ticket templates add <name>.`

### `templates delete <name>`

1. Confirm file exists. On missing, print `Template <name> not found.` and list available templates.
2. Ask: `Delete template <name>? (y/n)` — on `n`, stop.
3. Remove the file. Print: `Deleted ~/.claude/bigeye-plugin/ticket-templates/<name>.md.`

## Errors

| Condition | Behavior |
|---|---|
| Issue not found (CLI or MCP `search_issues`) | Print the CLI/MCP error text; suggest re-checking the display name; stop |
| Template file not found | List available templates (names only); suggest `/bigeye-ticket templates add <name>`; stop |
| Template I/O error (permissions, encoding) | Print the OS error + absolute file path; do not delete the file; stop |
| Unknown `{{variable}}` in template | Leave placeholder literal; append the single warning line per Step 8 item 6; continue rendering |
| MCP-only variable fetch failed / MCP down | Substitute `_(unavailable — MCP not configured)_`; add to `affected_vars` for the footer note per Step 8 item 5 |
| Wizard paste exceeds 200 lines | Stop reading; ask restart per wizard Step 6; do not touch disk |
| Wizard confirm `n` | Discard in-memory template; do not touch disk |

CLI auth and scope errors: follow `cli.md` Step G unchanged.

## Output example (MCP on)

```
Scope: profile=work-area · workspace=42 · sources=1

```
Service Request Name: BigEye #10921 — Freshness on warehouse.public.orders.created_at
Product Category: [Select appropriate category]
...
SR Type: Problem/Incident
Severity: Medium
```

-> Run /bigeye-rca 10921 if you have not already investigated.
```
````

- [ ] **Step 2: Verify file content**

Use the `Read` tool on `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-ticket/SKILL.md`. Confirm:
- Frontmatter includes `name: bigeye-ticket`, `user-invocable: true`
- Step 8 output order is preserved (Scope → fence → footer → warning → suggestion)
- `templates delete` section exists

Use `Grep` on the file for `improve.md` — expect at least 3 references.

- [ ] **Step 3: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye-ticket/SKILL.md
```

---

## Task 4: Create `skills/bigeye-improve/SKILL.md`

**Files:**
- Create: `skills/bigeye-improve/SKILL.md`

- [ ] **Step 1: Write the new skill file**

Write `skills/bigeye-improve/SKILL.md` with exactly this content:

````markdown
---
name: bigeye-improve
description: Use when the user wants to improve BigEye monitors on a table — tighten weak regexes, recommend better thresholds, or suggest new monitors grounded in column profile data. Read-only — output is markdown; deploy is a separate /bigeye-deploy invocation.
user-invocable: true
---

# BigEye Monitor Improvement

Analyze a table (or a single metric) and produce two kinds of recommendations:
1. **Weak existing monitors** — regex too permissive, lookback too short, thresholds too wide, missing schedule, or high false-positive rate.
2. **Missing coverage with concrete metric drafts** — grounded in BigEye's column profile when MCP is available, and in warehouse-sampled data when the user opts into heavy mode.

No writes. Output is markdown. Deploy is a separate user action via `/bigeye-deploy`.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for output formatting, `skills/bigeye/references/scope.md` for scope loading, `skills/bigeye/references/cli.md` for CLI invocation and MCP-availability detection, and `skills/bigeye/references/improve.md` for:
- §2 — the heuristics catalog (used in Step 1)
- §3 — the heavy-mode SQL templates (used in Step 5)
- §4 — the paste-parsing protocol (used in Steps 5–6)

## Arguments

Parse `$ARGUMENTS`. Remove `--profile`, `--no-scope`, `--workspace` scope flags first per `scope.md` Step B.

| Invocation | Behavior |
|---|---|
| `/bigeye-improve <table>` | Analyze all existing metrics + coverage on the table; heavy mode by default |
| `/bigeye-improve metric <metric_id>` | Single-metric deep analysis |
| `--light` | Skip the heavy-mode SQL loop (Steps 5–6) |
| `--sql-only` | Emit the heavy-mode SQL bundle, then stop (no paste-back second turn) |
| `--dimension <name>` | Limit coverage suggestions to one dimension (e.g., `freshness`, `validity`) |

`<table>` is either a bare name or a fully-qualified `schema.table` / `source.schema.table`. When ambiguous, ask which match the user meant.

## Procedure

### Step 0: Load scope and detect MCP

Follow `scope.md` Steps A–E then `cli.md` Step B. Per `scope.md` Step F, the user-named table is **unscoped** (always honored). Scope applies to MCP calls that accept filters.

If no table was named and the working profile has `table_names`/`table_ids`:
- Exactly one resolved table: use it. Tell the user which.
- Zero or multiple: ask which table to analyze. Never loop over all tables in a single heavy-mode run.

### Step 1: Existing monitors (always runs)

Enumerate metrics on the table via CLI per `cli.md` Step C:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> catalog get-metric-info -tn <table_name> -op "$TMPDIR"
```

Read every JSON file in `$TMPDIR`. For each metric, score against **all** heuristics in `improve.md` §2 (not just the cheap subset). For `HIGH_FALSE_POSITIVE_RATE`, additionally fetch issue history via:

```bash
bigeye -w <profile> issues get-issues -sn <schema> -op "$TMPDIR/issues"
```

Filter issue history to `status=ISSUE_STATUS_CLOSED`, `label=FALSE_POSITIVE`, `tableName=<table_name>`, `openedAt` within 30 days. Count per `metric_id`.

Produce a `weak_monitors` list: each entry carries `(metric_id, column, heuristic_id, severity, suggestion_text)`.

### Step 2: Missing coverage (MCP-only)

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=missing-coverage suggestions`. Skip this step only. Set `coverage_suggestions=[]` and continue.

If `MCP_AVAILABLE=true`:
  Call `mcp__bigeye__get_table_dimension_coverage` with `table_name: "{table_name}"`.
  Call `mcp__bigeye__get_column_dimension_coverage` with `table_name: "{table_name}"` (all columns).

  For each gap, draft a concrete metric spec: `(column, dimension, suggested_metric_type, parameters, rationale)`. Example rows: `(email, Validity, VALID_REGEX, pattern="<to be refined>", "Validity dimension has no existing metric")` or `(updated_at, Freshness, FRESHNESS, lookback_window=1d, "Table refreshes daily; no freshness monitor")`.

  If `--dimension <name>` was passed, filter `coverage_suggestions` to only that dimension.

### Step 3: Profile-based refinement (MCP-only)

If `MCP_AVAILABLE=false`:
  Skip this step. Annotate every row in `weak_monitors` and `coverage_suggestions` that would benefit from profile data with `(profile unavailable)` in its rationale column.

If `MCP_AVAILABLE=true`:
  For each column touched by Step 1 or 2, call `mcp__bigeye__get_table_profile` with `table_name: "{table_name}"`, `columns: [<col>]`. Use the returned profile to refine:
  - `null_rate=0.0` → suggest strict `PERCENT_NULL` threshold (e.g., `threshold: 0`)
  - `distinct_count < 10` on a `COUNT_DISTINCT`-targeted column → flag `METRIC_TYPE_MISMATCH` and suggest `CATEGORICAL`
  - Proposed regex → test against `sample_values` from the profile; if match rate < 95%, mark regex candidate as "needs heavy-mode data"

  Individual column-profile failures: mark that row `(profile unavailable for this column)` and continue.

### Step 4: Emit the primary report

Print in this exact order (sections with 0 rows are omitted):

```
Scope: {per scope.md Step G}

## Monitor Improvement Report — {schema}.{table_name}

### Weak Monitors ({count})
| Metric ID | Column | Why | Suggested change |
|---|---|---|---|
| {metric_id} | {col or "—"} | {heuristic_id}: {one-sentence reason} | {suggestion_text} |

### Coverage Suggestions ({count})
| Column | Missing dimension | Suggested metric | Rationale |
|---|---|---|---|
| {col} | {dim} | {metric_type with parameters} | {rationale} |

### Deploy hints
- /bigeye-deploy columns {col} --metric-type {TYPE}
- /bigeye-deploy freshness
- ... one line per actionable suggestion from Weak Monitors + Coverage Suggestions
```

If both `weak_monitors` and `coverage_suggestions` are empty, print:
`No improvements found — all monitors look healthy relative to current heuristics and {MCP on: "profile data"; MCP off: "available configuration data"}.`
Stop — do not emit Steps 5–6.

### Step 5: Heavy-mode SQL bundle (default; skipped by `--light`)

If `--light` was passed, skip this step and the next.

Otherwise, identify the columns that still need deeper reasoning: any column in `weak_monitors` flagged `THRESHOLD_DEFAULT` or `METRIC_TYPE_MISMATCH`, and any `coverage_suggestions` row whose suggested metric parameters are not yet final (e.g., regex still `<to be refined>`, threshold still a placeholder).

If the list is empty, skip to the end without Steps 5–6.

Otherwise, render the SQL bundle from `improve.md` §3 templates. For each relevant column, include the applicable templates (e.g., `NULL_DISTINCT` + `TOP_VALUES` for a regex refinement; `DISTRIBUTION_BUCKETS` + `DAILY_NULL_RATE` for a threshold refinement). Look up the warehouse dialect from the CLI's `catalog get-table-info` output (`warehouseType` field) to pick the right SQL form.

Emit the bundle, then:

If `--sql-only`: stop. Do not emit the paste protocol.

Otherwise: emit the paste protocol from `improve.md` §4.1 verbatim, then end the current turn.

### Step 6: Refined recommendations (heavy mode only, triggered by paste)

When the user sends the next message (containing pasted results), parse per `improve.md` §4.2.

If parse fails: ask for a re-paste of only the failed `-- query N` blocks. Preserve successfully-parsed sections across retries.

If the user sends `cancel` (case-insensitive prefix): per `improve.md` §4.3, produce a best-effort report from Steps 1–3 and append the cancellation line.

Otherwise: reason about the pasted results to produce:
- Tightened regex patterns derived from `TOP_VALUES` + `REGEX_MATCH` match rates
- Threshold ranges derived from `DISTRIBUTION_BUCKETS` and `DAILY_NULL_RATE`
- Metric-type revisions (e.g., `METRIC_TYPE_MISMATCH` confirmations)

Emit a second markdown block:

```
## Refined Recommendations
{Free-form markdown grouped by column — one paragraph per refined suggestion.}

### Deploy hints (updated)
- /bigeye-deploy columns {col} --metric-type {TYPE}   ← refined threshold: {value}
- ... only rows added or changed relative to the first block's Deploy hints

-> Suggested next: run the highest-impact deploy hint, then `/bigeye-triage` in ~1 hour.
```

The final `-> Suggested next:` line belongs to the **last** block emitted in the run — so `--light` and `--sql-only` print it at the end of Step 4's output; heavy mode prints it at the end of Step 6.

## MCP-absent behavior (summary)

| Mode | MCP on | MCP off |
|---|---|---|
| `--light` | Weak monitors + coverage suggestions + profile refinement | Weak monitors only (config heuristics); coverage suggestions skipped with the standard warning |
| default (heavy) | Weak + coverage + profile + SQL bundle + refined recommendations | Weak + SQL bundle + refined recommendations (no coverage, no profile) |
| `--sql-only` | Weak + coverage + profile + SQL bundle (stops) | Weak + SQL bundle (stops) |

Hard-fail only when the CLI itself cannot reach the workspace (auth or network). Use `cli.md` Step G text.

## Errors

| Condition | Behavior |
|---|---|
| Table not found | Print `bigeye catalog get-table-info` error verbatim; suggest `/bigeye-config show` to verify scope; stop |
| No metrics on table AND no MCP | Print `Nothing to improve — no existing monitors and MCP unavailable, so no coverage data. See bigeye-mcp-install.md.`; exit cleanly |
| MCP profile fetch partial failure | Continue with successful columns; mark failed-column rows `(profile unavailable for this column)` |
| Heavy-mode paste parse failure | Report which `-- query N` blocks failed; ask for re-paste of only those blocks; do not reset progress |
| User sends `cancel` mid heavy-mode | Produce best-effort report from Steps 1–3; append cancellation line per `improve.md` §4.3 |
| Unknown warehouse dialect for `DISTRIBUTION_BUCKETS` | Emit the comment-only skip placeholder from `improve.md` §3; continue |
````

- [ ] **Step 2: Verify file content**

Use the `Read` tool on `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-improve/SKILL.md`. Confirm:
- Frontmatter includes `name: bigeye-improve`, `user-invocable: true`
- All six procedure steps present (`Step 0:` through `Step 6:`)
- MCP-absent summary table present
- `improve.md` referenced in the "Before doing anything else" block

Use `Grep` for pattern `improve\.md` on the file; expect at least 5 matches.

- [ ] **Step 3: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye-improve/SKILL.md
```

---

## Task 5: Edit `skills/bigeye-coverage/SKILL.md`

**Files:**
- Modify: `skills/bigeye-coverage/SKILL.md`

- [ ] **Step 1: Insert new Step 4b before Step 5**

Use the `Edit` tool. Find this exact text (end of the existing Step 4):

```
If the `dimension` argument was provided, filter the gap list to only show gaps for that dimension.

### Step 5: Format Output
```

Replace with:

```
If the `dimension` argument was provided, filter the gap list to only show gaps for that dimension.

### Step 4b: Cheap weak-monitor scan

Using the monitor definitions already fetched in Step 1 and the issue history from Step 4, apply the "cheap" subset of the heuristics catalog in `skills/bigeye/references/improve.md` §2 (the rows with `Cheap? = yes`):

- `REGEX_PERMISSIVE` — pattern is in `{".+", ".*", ".+@.+", "[A-Za-z0-9]+"}`
- `LOOKBACK_MISSING` — no lookback or lookback_window = 0
- `SCHEDULE_MISSING` — no schedule configured
- `HIGH_FALSE_POSITIVE_RATE` — 3+ `FALSE_POSITIVE` closures in the last 30 days for this metric

Collect findings into `improvable_count` and a list `(metric_id, column, one-sentence reason)`. Do NOT fetch additional data — this step re-uses data already in hand from Steps 1 and 4.

### Step 5: Format Output
```

- [ ] **Step 2: Add the "Improvable Monitors" output section**

Use the `Edit` tool. Find this exact text:

```
### Suggested Monitor Deployment
```

Replace with:

```
### Improvable Monitors ({improvable_count})
{Only print this section when improvable_count > 0.}
- Metric #{metric_id} on {column or "table-level"}: {one-sentence reason}
{... up to 5 lines total}
{If improvable_count > 5:}
... and {improvable_count - 5} more.

### Suggested Monitor Deployment
```

- [ ] **Step 3: Add the new next-action line**

Use the `Edit` tool. Find this exact text (the closing block of the output template):

```
-> Run `/bigeye-deploy gaps` to deploy all suggested monitors
-> Run `/bigeye-deploy gaps --priority high` for high-priority only
```

Replace with:

```
-> Run `/bigeye-deploy gaps` to deploy all suggested monitors
-> Run `/bigeye-deploy gaps --priority high` for high-priority only
-> Run `/bigeye-improve {table_name}` for deep monitor recommendations (incl. weak-regex tightening, threshold tuning, distribution-aware suggestions)
```

- [ ] **Step 4: Verify content**

Use the `Read` tool on `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-coverage/SKILL.md`. Confirm:
- `### Step 4b: Cheap weak-monitor scan` appears between Step 4 and Step 5
- `### Improvable Monitors` appears before `### Suggested Monitor Deployment`
- The `/bigeye-improve {table_name}` next-action line appears at the end

Use `Grep` on the file for `improve\.md` — expect at least 1 match (the §2 reference in Step 4b).

- [ ] **Step 5: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye-coverage/SKILL.md
```

---

## Task 6: Edit `skills/bigeye-triage/SKILL.md`

**Files:**
- Modify: `skills/bigeye-triage/SKILL.md`

- [ ] **Step 1: Append one bullet to Step 5**

Use the `Edit` tool. Find this exact text at the end of Step 5:

```
### Step 5: Suggest Next Actions

Always end with:
- If clusters detected: "Run `/bigeye-incidents auto` to group related issues"
- Top critical issue: "Run `/bigeye-rca {issue}` for root cause analysis"
- If many NEW issues: "Run `/bigeye-incidents auto` then acknowledge clusters"
```

Replace with:

```
### Step 5: Suggest Next Actions

Always end with:
- If clusters detected: "Run `/bigeye-incidents auto` to group related issues"
- Top critical issue: "Run `/bigeye-rca {issue}` for root cause analysis"
- If many NEW issues: "Run `/bigeye-incidents auto` then acknowledge clusters"
- For any issue you want to hand to a data vendor: `/bigeye-ticket <display_name>`
```

- [ ] **Step 2: Verify content**

Use `Grep` on `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye-triage/SKILL.md` for pattern `bigeye-ticket` — expect exactly 1 match.

- [ ] **Step 3: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye-triage/SKILL.md
```

---

## Task 7: Edit the `/bigeye` router

**Files:**
- Modify: `skills/bigeye/SKILL.md`

- [ ] **Step 1: Add two rows to the intent table**

Use the `Edit` tool. Find this exact text:

```
| "group issues", "create incident", "merge issues", "incident" | Skill: `bigeye-incidents` |
```

Replace with:

```
| "group issues", "create incident", "merge issues", "incident" | Skill: `bigeye-incidents` |
| "draft a ticket", "write a ticket for issue X", "vendor ticket", "SR", "service request" | Skill: `bigeye-ticket` with args passed through |
| "improve monitors", "tighten regex", "better thresholds", "recommend monitors", "weak monitors" | Skill: `bigeye-improve` with args passed through |
```

- [ ] **Step 2: Add two rows to the Ambiguous Intent menu**

Use the `Edit` tool. Find this exact text:

```
6. **Incidents** — Group related issues (`/bigeye-incidents`)
```

Replace with:

```
6. **Incidents** — Group related issues (`/bigeye-incidents`)
7. **Draft a vendor ticket** — render a markdown ticket for an issue (`/bigeye-ticket`)
8. **Improve monitors** — tighten weak monitors, recommend new ones (`/bigeye-improve`)
```

- [ ] **Step 3: Verify content**

Use `Grep` on `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/SKILL.md` for `bigeye-ticket` — expect exactly 2 matches. For `bigeye-improve` — expect exactly 2 matches.

- [ ] **Step 4: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye/SKILL.md
```

---

## Task 8: Edit `skills/bigeye/references/scope.md`

**Files:**
- Modify: `skills/bigeye/references/scope.md`

- [ ] **Step 1: Add two rows to the Step F applicability table**

Use the `Edit` tool. Find this exact text:

```
| `bigeye-morning-report` (agent) | Same as triage — fully scoped |
```

Replace with:

```
| `bigeye-morning-report` (agent) | Same as triage — fully scoped |
| `bigeye-ticket` | Primary issue lookup is **unscoped** (user named a specific issue). Scope applies only to MCP lineage/related calls for `{{downstream_tables}}` / `{{related_issues}}` |
| `bigeye-improve` | Table argument is unscoped when named explicitly. Scope applies to MCP profile/coverage calls if their schema accepts filters; no table-list enumeration (user always names one, or the profile resolves to a single in-scope table) |
```

- [ ] **Step 2: Verify content**

Use `Grep` on `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/skills/bigeye/references/scope.md` for `bigeye-ticket` — expect exactly 1 match. For `bigeye-improve` — expect exactly 1 match.

- [ ] **Step 3: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add skills/bigeye/references/scope.md
```

---

## Task 9: Edit `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add two rows to the Commands table**

Use the `Edit` tool. Find this exact text:

```
| `/bigeye-incidents [ids/auto]` | Group related issues into incidents |
```

Replace with:

```
| `/bigeye-incidents [ids/auto]` | Group related issues into incidents |
| `/bigeye-ticket [issue]` | Draft a copy-pasteable markdown vendor ticket |
| `/bigeye-improve [table]` | Deep recommendations for weak monitors and missing coverage |
```

- [ ] **Step 2: Add the ticket-templates note under Configuration**

Use the `Edit` tool. Find this exact text (the paragraph currently ending "Every skill applies the active profile automatically; override per-invocation with `--profile <name>`, `--no-scope`, or `--workspace <id>`."):

```
**Scope profiles (per-user):** Run `/bigeye-config init` once after installing the plugin. This creates `~/.claude/bigeye-plugin/profiles.json` with your workspace ID and optional filters (data sources, tables, schemas, tags). Every skill applies the active profile automatically; override per-invocation with `--profile <name>`, `--no-scope`, or `--workspace <id>`.
```

Replace with:

```
**Scope profiles (per-user):** Run `/bigeye-config init` once after installing the plugin. This creates `~/.claude/bigeye-plugin/profiles.json` with your workspace ID and optional filters (data sources, tables, schemas, tags). Every skill applies the active profile automatically; override per-invocation with `--profile <name>`, `--no-scope`, or `--workspace <id>`.

**Ticket templates:** `/bigeye-ticket` reads and writes `~/.claude/bigeye-plugin/ticket-templates/<name>.md`. Seeded with a `default.md` on first run. Manage via `/bigeye-ticket templates add/edit/delete/list`.
```

- [ ] **Step 3: Verify content**

Use `Grep` on `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/README.md` for `/bigeye-ticket` — expect at least 3 matches (commands row, configuration note, templates paragraph). For `/bigeye-improve` — expect at least 1 match.

- [ ] **Step 4: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add README.md
```

---

## Task 10: Version bump 0.2.0 → 0.3.0

**Files:**
- Modify: `.claude-plugin/marketplace.json`
- Modify: `pyproject.toml`

- [ ] **Step 1: Bump `marketplace.json`**

Use the `Edit` tool on `.claude-plugin/marketplace.json`. Find:

```
      "version": "0.2.0",
```

Replace with:

```
      "version": "0.3.0",
```

- [ ] **Step 2: Bump `pyproject.toml`**

Use the `Edit` tool on `pyproject.toml`. Find:

```
version = "0.2.0"
```

Replace with:

```
version = "0.3.0"
```

- [ ] **Step 3: Verify**

Use `Grep` with pattern `0\.3\.0` on both files — expect 1 match each. Use `Grep` with pattern `0\.2\.0` on both files — expect 0 matches in each.

- [ ] **Step 4: Stage**

```bash
git -C /Users/andriik-mbp/PycharmProjects/bigeye-plugin add .claude-plugin/marketplace.json pyproject.toml
```

---

## Task 11: Manual verification

No automated tests. Run these scenarios against a real Bigeye workspace after the user has reloaded the plugin. Report pass/fail per item.

- [ ] **Scenario 11.1: `/bigeye-ticket` first-run seeding**

1. Move any existing `~/.claude/bigeye-plugin/ticket-templates/` aside (or delete if you're sure).
2. Run `/bigeye-ticket <known-issue>` against a real issue in your workspace.
3. Expect: the "Seeded default template..." one-liner, then a rendered ticket inside a triple-backtick fence.
4. Confirm `~/.claude/bigeye-plugin/ticket-templates/default.md` now exists with the §3.10 content.

- [ ] **Scenario 11.2: `/bigeye-ticket templates` wizard round-trip**

1. Run `/bigeye-ticket templates add monday`. Paste a 5-line template containing `{{table_name}}`, `{{dimension}}`, and one deliberately unknown `{{totally_fake}}`. Finish with `EOF`.
2. Expect the usage summary lists `{{table_name}}` and `{{dimension}}` as used, `{{totally_fake}}` as unknown. Confirm save.
3. Run `/bigeye-ticket templates list` — expect `monday` in the table.
4. Run `/bigeye-ticket --template monday <issue>` — expect render with `{{totally_fake}}` literal + a warning line.
5. Run `/bigeye-ticket templates edit monday`, remove `{{totally_fake}}`, save. Render again — expect no warning line.
6. Run `/bigeye-ticket templates delete monday` — expect file removed.

- [ ] **Scenario 11.3: `/bigeye-ticket` with MCP off**

1. Temporarily disable the Bigeye MCP server (or run on a machine where it's not configured).
2. Run `/bigeye-ticket <known-issue>`.
3. Expect: `{{downstream_tables}}`, `{{related_issues}}`, `{{resolution_steps}}` rendered as `_(unavailable — MCP not configured)_`, with one footer note line listing them.

- [ ] **Scenario 11.4: `/bigeye-ticket --template nonexistent`**

1. Run `/bigeye-ticket --template banana <issue>`.
2. Expect: template-not-found error listing available templates; no render.

- [ ] **Scenario 11.5: `/bigeye-ticket --internal-id`**

1. With MCP off, run `/bigeye-ticket --internal-id <known-internal-id>`.
2. Expect: successful render (MCP display-name lookup was bypassed).

- [ ] **Scenario 11.6: `/bigeye-improve --light` (MCP off)**

1. With MCP off, run `/bigeye-improve <known-table> --light` on a table you know has at least one weak monitor (e.g., a `VALID_REGEX` with pattern `.+`).
2. Expect: Weak Monitors section populated, no Coverage Suggestions section, no SQL bundle, no Refined Recommendations.

- [ ] **Scenario 11.7: `/bigeye-improve --light` (MCP on)**

1. With MCP on, run `/bigeye-improve <known-table> --light`.
2. Expect: Weak Monitors + Coverage Suggestions sections both populated; profile-refined rationale strings on Coverage Suggestions rows; no SQL bundle.

- [ ] **Scenario 11.8: `/bigeye-improve` default (heavy) — first turn**

1. Run `/bigeye-improve <known-table>`.
2. Expect: primary report + SQL bundle + paste protocol delimiter. Turn ends.
3. Verify the SQL dialect matches your warehouse type (e.g., `REGEXP_LIKE` for Snowflake, `~` for Postgres).

- [ ] **Scenario 11.9: `/bigeye-improve` default (heavy) — second turn paste**

1. From 11.8, run the queries manually against your warehouse.
2. Paste results under `--- BEGIN RESULTS ---`, then send.
3. Expect: Refined Recommendations section + updated Deploy hints. Final `-> Suggested next:` line appears.

- [ ] **Scenario 11.10: `/bigeye-improve` heavy — corrupted paste**

1. Repeat 11.8. In the paste, deliberately corrupt one `-- query N` block.
2. Send.
3. Expect: the skill asks for a re-paste of only that block; other blocks are not re-requested.

- [ ] **Scenario 11.11: `/bigeye-improve` heavy — cancel**

1. Repeat 11.8. In the paste, send the single word `cancel`.
2. Expect: best-effort report from Steps 1–3 + one line noting Deep Refinement cancelled.

- [ ] **Scenario 11.12: `/bigeye-improve metric <id>`**

1. Run `/bigeye-improve metric <known-weak-metric-id>`.
2. Expect: a one-row Weak Monitors report (no Coverage Suggestions).

- [ ] **Scenario 11.13: `/bigeye-improve --sql-only`**

1. Run `/bigeye-improve <known-table> --sql-only`.
2. Expect: primary report + SQL bundle, no paste delimiter. Turn ends.

- [ ] **Scenario 11.14: `/bigeye-improve` with no table and MCP off**

1. With MCP off and no metrics on the target table, run `/bigeye-improve <empty-table>`.
2. Expect: exactly the line `Nothing to improve — no existing monitors and MCP unavailable, so no coverage data. See bigeye-mcp-install.md.` and clean exit.

- [ ] **Scenario 11.15: `/bigeye-coverage` regression + addition**

1. Run `/bigeye-coverage` on a table with at least one known-weak monitor.
2. Expect: existing output intact; new `### Improvable Monitors` section appears before Suggested Monitor Deployment; new `-> Run /bigeye-improve <table_name>` next-action line appears at the end.
3. Run `/bigeye-coverage` on a table with no weak monitors.
4. Expect: the `### Improvable Monitors` section is omitted; the `-> Run /bigeye-improve` line still appears.

- [ ] **Scenario 11.16: `/bigeye-triage` next-action**

1. Run `/bigeye-triage`.
2. Expect: Step 5 output ends with the bullet `- For any issue you want to hand to a data vendor: /bigeye-ticket <display_name>` after the existing bullets.

- [ ] **Scenario 11.17: Router intent**

1. Run `/bigeye draft a ticket for 10921`. Expect routing to `/bigeye-ticket 10921`.
2. Run `/bigeye improve orders table`. Expect routing to `/bigeye-improve orders`.
3. Run `/bigeye what's broken`. Expect routing to `/bigeye-triage` (regression).

- [ ] **Scenario 11.18: Version + README**

1. Use `Read` on `.claude-plugin/marketplace.json`: `"version"` field reads `"0.3.0"`.
2. Use `Read` on `pyproject.toml`: `version` line reads `version = "0.3.0"`.
3. Use `Grep` on `README.md` for `/bigeye-ticket` (at least 3 matches) and `/bigeye-improve` (at least 1 match).

Report any failures; the user owns decisions on whether each blocks merge.

---

## Self-Review Notes (for the implementer)

If executing this plan via `subagent-driven-development`, the subagent for each task should be given:
- The task section from this plan
- Read access to the spec (`docs/superpowers/specs/2026-04-23-bigeye-intelligence-layer-design.md`)
- Read access to `improve.md` once Task 1 is done

Task 1 is the biggest (writes the whole shared reference in one shot). Every subsequent task is materially smaller.

No task depends on any task numbered higher than itself. Tasks 5–10 can run in parallel if you want to fan out after Tasks 1–4 are complete, but the sequencing in order is the safer default.
