---
name: bigeye-improve
description: Use when the user wants to improve BigEye monitors on a table — tighten weak regexes, recommend better thresholds, or suggest new monitors grounded in column profile data. Read-only — output is markdown; deploy is a separate /bigeye-deploy invocation.
user-invocable: true
---

# BigEye Monitor Improvement

What it does: scores existing monitors against quality heuristics, suggests missing-coverage monitor drafts, and (in heavy mode) emits warehouse SQL for the user to run, then refines recommendations from pasted results. Read-only — no writes.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`. Heuristics, SQL templates, and paste-parsing rules live in `skills/bigeye/references/improve.md`.

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `<table>` | Analyze the named table; heavy-mode by default | `/bigeye-improve orders` |
| (no arg) | Use `state.json.last_table`; if empty, ask | `/bigeye-improve` |
| `metric <metric_id>` | Single-metric deep analysis | `/bigeye-improve metric 17321` |
| `--light` | Skip heavy-mode SQL loop (Steps 5–6) | `/bigeye-improve orders --light` |
| `--sql-only` | Emit SQL bundle then stop (no paste-back) | `/bigeye-improve orders --sql-only` |
| `--dimension <name>` | Limit coverage suggestions to one dimension | `/bigeye-improve orders --dimension validity` |

Global flags — see `output.md`.

## Procedure

1. Follow `preamble.md` Steps 1–7. Per Step 5, the user-named table is **unscoped** — scope applies only to MCP calls that accept filters.

2. Resolve the target table:
   - Argument given → use it (ambiguous bare name → ask).
   - No argument:
     - `state.json.last_table` set → use it. Print: `Improving {fq} (last table from prior session).`
     - Else if profile resolves to exactly one table → use it (tell the user).
     - Else → ask which table to analyze. Never loop over all tables in a single heavy-mode run.

3. **Existing monitors (always runs):**
   ```bash
   TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
   trap 'rm -rf "$TMPDIR"' EXIT
   bigeye -w <profile> catalog get-metric-info -tid <table_id> -op "$TMPDIR"
   ```
   For each metric JSON, score against **all** heuristics in `improve.md` §2. For `HIGH_FALSE_POSITIVE_RATE`, fetch issue history:
   ```bash
   bigeye -w <profile> issues get-issues -sn <schema> -op "$TMPDIR/issues"
   ```
   Filter to `status=CLOSED`, `label=FALSE_POSITIVE`, `tableName=<table>`, `openedAt` within 30 days. Count per `metric_id`.

   Build `weak_monitors` = `[(metric_id, column, heuristic_id, severity, suggestion_text), ...]`.

4. **Missing coverage (MCP-only):**
   - `MCP_AVAILABLE=false`: per Step 7.B with `feature_name=missing-coverage suggestions`. Skip; set `coverage_suggestions = []`.
   - `MCP_AVAILABLE=true`: `get_table_dimension_coverage` + `get_column_dimension_coverage` for the table. For each gap, draft `(column, dimension, suggested_metric_type, parameters, rationale)`. With `--dimension`, filter to that dimension.

5. **Profile-based refinement (MCP-only):**
   - `MCP_AVAILABLE=false`: skip. Annotate every row in `weak_monitors` and `coverage_suggestions` that would benefit from profile data with `(profile unavailable)` in the rationale.
   - `MCP_AVAILABLE=true`: for each touched column, `mcp__bigeye__get_table_profile` with `table_name`, `columns`. Refine per `improve.md` §2 rules (null rate, distinct count, regex match rate against sample values).

6. **Emit primary report:**
   ```
   {scope pill}
   ## Monitor Improvement Report — {schema}.{table_name}

   ### Weak Monitors ({count})
   | Metric ID | Column | Why | Suggested change |
   |---|---|---|---|
   | ... | ... | ... | ... |

   ### Coverage Suggestions ({count})
   | Column | Missing dimension | Suggested metric | Rationale |
   |---|---|---|---|

   ### Deploy hints
   - /bigeye-deploy columns {col} --metric-type {TYPE}
   - /bigeye-deploy freshness
   - ...
   ```
   Sections with 0 rows are omitted. If both are empty, print `No improvements found — all monitors look healthy relative to current heuristics and {MCP on: "profile data" / MCP off: "available configuration data"}.` then footer + state-write + exit (skip Steps 7–8).

7. **Heavy-mode SQL bundle (default; skipped by `--light`):**
   Identify columns still needing deeper reasoning (any `weak_monitors` row flagged `THRESHOLD_DEFAULT`/`METRIC_TYPE_MISMATCH`; any `coverage_suggestions` row whose params aren't final). Empty list → skip Steps 7–8.
   Otherwise, render the SQL bundle from `improve.md` §3 templates. Look up the warehouse dialect from CLI's `catalog get-table-info` (`warehouseType` field). Print numbered progress markers `[N/M]` per `output.md` §Progress indicators. Emit the bundle.
   With `--sql-only`: stop after the bundle. With heavy default: emit the paste protocol from `improve.md` §4.1 verbatim, then end the current turn.

8. **Refined recommendations (heavy mode only, triggered by paste):**
   On the next user message, parse per `improve.md` §4.2. Parse failure → ask for a re-paste of only failed `-- query N` blocks; preserve successful sections.
   `cancel` → produce a best-effort report from Steps 3–5 + the cancellation line per `improve.md` §4.3.
   Else: emit
   ```
   ## Refined Recommendations
   {one paragraph per refined suggestion, grouped by column}

   ### Deploy hints (updated)
   - /bigeye-deploy columns {col} --metric-type {TYPE}   <- refined threshold: {value}
   - ...
   ```

9. Footer (always — printed at the end of the **last** block emitted):
   ```
   Next: /bigeye-deploy columns {top_col} --metric-type {TYPE}     ({weak_count} weak monitors / {gap_count} gaps)
   More: /bigeye-coverage {table}  ·  /bigeye-table {table}  ·  /bigeye-deploy gaps
   ```

## State persistence

On the **last** successful render of the run (Step 6 for `--light`/`--sql-only`/empty result; Step 8 for heavy mode), follow `preamble.md` Step 8.B for the `bigeye-improve` row:
- Set `state.json.last_table = "<schema.table>"`.
- Append `{ skill: "bigeye-improve", at: <iso8601> }` to `state.json.tables[<fq>].actions`.
- Update `first_seen` / `last_seen`.

Then run pruning per Step 8.C.

## MCP-absent matrix

| Mode | MCP on | MCP off |
|---|---|---|
| `--light` | weak + coverage + profile | weak only; coverage skipped |
| default (heavy) | weak + coverage + profile + SQL + refined | weak + SQL + refined (no coverage, no profile) |
| `--sql-only` | weak + coverage + profile + SQL (stops) | weak + SQL (stops) |

Hard-fail only when CLI itself cannot reach the workspace (auth/network) — per `preamble.md` Step 7.D.

## Errors

| Condition | Behavior |
|---|---|
| Table not found | Print CLI error verbatim per Step 7.D; suggest `/bigeye-config show`; stop |
| No metrics on table AND MCP off | Print one line `Nothing to improve — no existing monitors and MCP unavailable, so no coverage data. See bigeye-mcp-install.md.`; clean exit |
| MCP profile fetch partial failure | Continue with successful columns; mark failed rows `(profile unavailable for this column)` |
| Heavy-mode paste parse failure | Report failed `-- query N` blocks; ask for re-paste of only those; preserve progress |
| User sends `cancel` mid heavy-mode | Best-effort report from Steps 3–5 + cancellation line per `improve.md` §4.3 |
| Unknown warehouse dialect for `DISTRIBUTION_BUCKETS` | Emit comment-only skip placeholder per `improve.md` §3; continue |
