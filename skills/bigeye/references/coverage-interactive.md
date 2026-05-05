# Coverage — interactive batch proposal

Used by `/bigeye-coverage <table>` (v0.5).

## Inputs

- table — required (resolve to `table_id` via MCP; ambiguity → user picks)
- active profile + `monitored_rules` (limits which dimensions are considered)

## Procedure

1. Resolve target table → `table_id`.
2. `mcp__bigeye__get_table_profile(table_id)` → per-column profile (null %, distinct count, cardinality, format samples, numeric / length stats).
3. `mcp__bigeye__get_table_dimension_coverage(table_id)` → existing monitor coverage.
4. Identify uncovered or weakly-covered columns. Filter to dimensions in `profile.monitored_rules`. Order: PK → FK → indexed → numeric → categorical → text.
5. Iterate columns in batches of 3:
   1. Show the auto-detected profile for the column:
      ```
      Column: {name}
        type:        {data_type}
        null_pct:    {x}%
        distinct:    {n} ({x}% of rows)
        format hint: {regex matched on >95% of samples, or "—"}
        samples:     [{up to 5}]
      ```
   2. Ask: `What does this column hold?` Provide the auto-guess summary + accepted answer forms:
      - `confirm` (auto-guess is correct)
      - `<free text>` describing the data (e.g. `work emails @company.com only`)
      - `skip` (no monitor for this column)
   3. Map (auto-guess + user constraint + profile) → fitted monitor candidates:
      - REGEX_MATCH if the user describes a format pattern.
      - COMPLETENESS if `null_pct > 0` and user confirms non-nullable.
      - UNIQUENESS if user confirms unique.
      - FRESHNESS if column is timestamp + user confirms it tracks last update.
      - VALUE_RANGE if numeric + user gives bounds.
   4. Render fitted candidates with reasoning + doc URL citation. Ask: `Queue which? (comma list / all / none)`. Each fitted candidate's reasoning ends with a `Source: …` line. Delegate URL resolution to `bigeye-docs-grounding` with the candidate dimension as the topic.
   5. Append picked items to the in-memory queue.
6. After all columns processed (or user types `stop`), render the bulk deploy block:
   ```
   Queued monitors for {schema}.{table_name}:
     1. {dimension} on {column}        — reasoning: {one sentence}
     2. ...
   Deploy: /bigeye-deploy gaps {table} --queued
   ```
7. Read-only output. User runs deploy separately.

## Resumability

Per-column queue + last-processed column saved to `state.tables[<fq>].coverage_queue`. `/bigeye-coverage` no-arg resumes from the next unprocessed column.

## Errors

- Column profile fetch fails → mark `(profile unavailable for {column})`. Continue with the rest of the batch.
- User types unparseable answer twice → skip the column with `(skipped — unparsed input)`.
