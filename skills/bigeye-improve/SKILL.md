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
bigeye -w <profile> catalog get-metric-info -tid <table_id> -op "$TMPDIR"
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
