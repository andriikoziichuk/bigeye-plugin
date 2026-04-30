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
| `{{status}}` | CLI issue JSON `status` mapped per `output.md` §Status display mapping | no |
| `{{priority}}` | CLI issue JSON `priority` mapped per `output.md` §Priority display mapping | no |
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
