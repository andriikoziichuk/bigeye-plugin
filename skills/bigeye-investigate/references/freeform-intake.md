# Freeform-Mode Intake Procedure

Invoked by `/bigeye-investigate` when the arg classifier in `SKILL.md` selects freeform mode. Runs in the main thread (not in the subagent). Output: a fully-built `InvestigationRequest` with `mode: "freeform"` ready to dispatch.

## Phase F0 — Parse raw input

Shell out to `python -m tools.freeform_intake parse '<prose>' '<flags_json>'` if a CLI wrapper exists; otherwise call the equivalent of `tools.freeform_intake.parse(prose, flags)` and capture the returned dict.

Inputs:
- `prose` — the full positional argument the user passed (may include fenced SQL).
- `flags` — `{ "table": ..., "since": ..., "type": ... }` from the parsed flag set.

Output dict shape (= `IntakeFacts` + `seed_sql`):

```
{ "table_fq": str|null, "column": null,
  "monitor_where": str|null, "issue_type": str,
  "time_column": "loaded_at", "user_prose": str,
  "seed_sql": str|null }
```

Flag overrides win. The parser is best-effort; it never errors.

## Phase F1 — Required-fields gate

Required for engine dispatch: `table_fq`, `monitor_where`, `issue_type`.

Up to **three** rounds. Each round asks ONE question, in order:

**Round 1 (if `table_fq` is null):**
```
Which table is this about? (e.g. SCHEMA.TABLE)
```
Accept the answer verbatim. If still empty after the answer, continue with `table_fq = null`.

**Round 2 (if `monitor_where` is null):**
```
What time window or filter scopes the issue? Options:
  [1] last 7 days   [2] last 24 hours   [3] all rows
  [4] enter custom WHERE clause
Default time column: loaded_at — change with: column=<name>
```
Map answers:
- `1` → `loaded_at >= DATEADD(day, -7, CURRENT_DATE)`
- `2` → `loaded_at >= DATEADD(hour, -24, CURRENT_TIMESTAMP())`
- `3` → `1=1`
- `4` → accept the next user line as a raw WHERE fragment.
- `column=NAME` prefix → swap `loaded_at` for `NAME` before applying the rest.

**Round 3 (if `issue_type == "custom"` AND prose had no symptom keyword):**
```
Which kind of issue?
  [1] freshness  [2] volume  [3] null  [4] distribution  [5] schema  [6] custom
```
Map `1..6` to the six issue types.

After three rounds, if any required field is still missing:

```
Error: not enough info to investigate.
Fix:   /bigeye-investigate "<your description>" --table SCHEMA.TABLE --since 7d --type volume
Why:   need table, time scope, and issue type to run hypotheses.
```
Stop. Do not write state. Do not dispatch the subagent.

## Phase F2 — Guard pasted SQL

If `seed_sql` is non-null:

```
python -m tools.readonly_guard "<seed_sql>"
```

Non-zero exit → print:

```
Error: pasted SQL rejected by read-only guard: <stderr>.
Fix:   remove the write statement and re-run.
```
Stop.

Zero exit → keep `seed_sql` for the request.

## Phase F3 — Confirm intake

Print:

```
Freeform investigation intake:
  Table:        {table_fq}
  Filter:       {monitor_where}
  Issue type:   {issue_type}
  Pack:         {pack_override or "_default (tag lookup pending; resolved at engine Phase 2)"}
  Budget:       {budget}
  Seed query:   {"yes (will run as query #0)" if seed_sql else "no"}
Proceed? [y/n]
```

- `y` → build `InvestigationRequest`:
  ```
  {
    "request_id": "<uuid>",
    "issue_ref": "D-" + uuid4().hex[:4],
    "internal_id_flag": false,
    "snow_profile": <resolved>,
    "pack_override": <from --pack>,
    "budget": <from --budget or 10>,
    "scope": <from active profile>,
    "mode": "freeform",
    "intake_facts": { ...IntakeFacts..., "opened_at": "<now iso>" },
    "seed_query": { "sql": seed_sql, "source": "user-pasted" } if seed_sql else null
  }
  ```
- `n` → re-enter Phase F1 round 1 with prior answers preserved (do NOT re-run F0; the parsed dict is still valid).

## Hand-off

After F3 returns `y`, the skill dispatches the `bigeye-investigator` subagent with the synthesized `InvestigationRequest`. The subagent follows `engine.md` exactly — Phase 1 branches on `mode`, the rest is identical to issue mode.
