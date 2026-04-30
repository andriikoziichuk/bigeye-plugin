---
name: bigeye-coverage
description: Use when the user wants to find monitoring gaps, check which columns or dimensions lack monitors, or assess overall monitoring coverage on their table
user-invocable: true
---

# BigEye Coverage Analysis

What it does: scores dimension coverage on a table (or the in-scope tables), prioritizes gaps using past issue history, and surfaces cheap weak-monitor findings inline.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`.

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `<table>` | Run coverage on a named table (bare, `schema.table`, or `source.schema.table`) | `/bigeye-coverage orders` |
| (no arg) | Use `state.json.last_table`. If empty, run on every in-scope table from the active profile. | `/bigeye-coverage` |
| `columns <c1>,<c2>` | Coverage limited to specific columns | `/bigeye-coverage columns email,phone` |
| `dimension <name>` | Filter gap list by dimension | `/bigeye-coverage dimension validity` |

Global flags — see `output.md`.

## Procedure

1. Follow `preamble.md` Steps 1–7.

2. Resolve the target tables:
   - Argument given → use it (single table). If a bare name needs MCP resolution and MCP is off, hard-fail with `feature_name=table-name resolution` and a Fix `/bigeye-coverage <source>.<schema>.<table>`.
   - No argument:
     - If `state.json.last_table` is set: use it. Print one line: `Coverage on {fq} (last table from prior session).`
     - Else: enumerate in-scope tables from the active profile (`table_ids` + resolved `table_names`). If none, fall back to `data_source_ids` and ask the user which table when more than one matches. Empty profile under `--no-scope` → ask.

3. For each target table, get dimension coverage (MCP):
   - `MCP_AVAILABLE=false`: per Step 7.B emit the warning with `feature_name=dimension coverage scoring` and a Fix line `Coverage scoring has no CLI equivalent — see bigeye-mcp-install.md.` Hard-stop.
   - `MCP_AVAILABLE=true`: `mcp__bigeye__get_table_dimension_coverage` with `table_name`. Capture overall %, per-dimension status, suggested metrics.

4. Get dimension taxonomy: `mcp__bigeye__list_dimensions` (categories: PIPELINE_RELIABILITY vs DATA_QUALITY).

5. If `columns <list>` was given: `mcp__bigeye__get_column_dimension_coverage` for those columns.

6. Fetch past issues via CLI:
   ```bash
   TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
   trap 'rm -rf "$TMPDIR"' EXIT
   bigeye -w <profile> issues get-issues {-wid <id>} {-sn <name>} -op "$TMPDIR"
   ```
   Parse JSON; filter to issues with `tableName == target_table`; keep `NEW`, `ACKNOWLEDGED`, `CLOSED` (last 30 days). Build the per-column issue counts.

7. Prioritize gaps:
   - **HIGH**: column has issues in last 30d AND missing dimensions
   - **MEDIUM**: no recent issues but missing critical dimensions (Freshness, Volume, Uniqueness, Completeness)
   - **LOW**: missing only non-critical dimensions (Distribution, Format)

   `dimension <name>` arg → filter the gap list to that dimension.

8. Cheap weak-monitor scan: apply heuristics from `skills/bigeye/references/improve.md` §2 with `Cheap? = yes` (REGEX_PERMISSIVE, LOOKBACK_MISSING, SCHEDULE_MISSING, HIGH_FALSE_POSITIVE_RATE) using monitor data already in hand from Step 3 + issue history from Step 6. Collect into `improvable_count` and a list of `(metric_id, column, one-sentence reason)`. No additional fetches.

9. Render:
   ```
   {scope pill}
   ## Coverage Report — {schema}.{table_name}

   ### Overall Score: {percent}% ({covered} of {total} dimension-column pairs covered)

   ### Table-Level Coverage
   | Dimension | Category | Status | Monitor |
   |---|---|---|---|
   | Freshness | Pipeline Reliability | Covered/GAP | {metric_name or —} |
   | ... | ... | ... | ... |

   ### Top Column Gaps (prioritized)
   | Column | Missing Dimensions | Past Issues (30d) | Priority |
   |---|---|---|---|
   | {col} | {dims} | {count} | HIGH |

   {Top 20 columns under Brief; --full shows all. "(N more — add --full to see all)" if truncated.}

   ### Improvable Monitors ({improvable_count})
   {only print if improvable_count > 0; up to 5 lines}
   - Metric #{id} on {column or "table-level"}: {reason}
   ... and {improvable_count - 5} more.

   ### Suggested Monitor Deployment
   {count} monitors recommended:
   - {N} {Dimension} monitors ({columns})
   - ...
   ```

10. Footer:
    ```
    Next: /bigeye-deploy gaps --priority high     ({high_count} high-priority gaps)
    More: /bigeye-improve {table}  ·  /bigeye-deploy gaps  ·  /bigeye-table {table}
    ```
    If `improvable_count > 0`: change `Next:` to `Next: /bigeye-improve {table}     ({improvable_count} weak monitors)`.

## State persistence

On successful render, follow `preamble.md` Step 8.B for the `bigeye-coverage` row:
- Set `state.json.last_table = "<schema.table>"` (or the fully-qualified target).
- Append `{ skill: "bigeye-coverage", at: <iso8601> }` to `state.json.tables[<fq>].actions`.
- Update `first_seen` (if absent) and `last_seen`.

Then run pruning per Step 8.C.

## Errors

CLI / scope / parse errors per `preamble.md` Step 7.D.
MCP-absent: per Step 7.B as documented in Step 3 above.
