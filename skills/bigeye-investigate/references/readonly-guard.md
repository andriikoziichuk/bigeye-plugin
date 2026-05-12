# Read-Only SQL Guard

Two-layer defense. Both must pass for any Snowflake call from the investigator.

## Layer 1 — engine-side (this guard)

Implemented in `tools/readonly_guard.py`. Invoked by the subagent before every `snow sql` call.

**CLI contract:**

```bash
python -m tools.readonly_guard "<sql>"
```

Exit codes:
- `0` — SQL is read-only and safe to execute.
- `1` — SQL rejected. Reason on stderr.
- `2` — misuse (no arg).

**Subagent behavior on rejection:**

1. Do NOT call `snow sql`.
2. Append `{ "kind": "guard_reject", "sql": "<sql>", "reason": "<stderr>" }` to trace.
3. Budget is NOT consumed.
4. Continue with the next hypothesis.
5. If three guard rejects accumulate in a row, abort the engine loop with `{ "kind": "engine_abort", "reason": "3 consecutive guard rejects" }` and return `diagnosis.confidence = "low"`.

**What the guard rejects:**

- Non-`SELECT`/`WITH` first token (e.g. `EXPLAIN`, `DESC`, `SHOW`).
- Any of: `insert`, `update`, `delete`, `merge`, `create`, `drop`, `alter`, `truncate`, `grant`, `revoke`, `copy`, `put`, `get`, `use`, `call`, `execute`, `unload`, `stream`, `task`, `procedure` (whole-word, including after a `;`).
- `SELECT ... INTO` (creates a table via implicit DDL on some warehouses).
- Multi-statement queries.
- Empty / whitespace-only / comment-only queries.

**What the guard does NOT do:**

- Does not parse SQL into an AST. It is a textual denylist.
- Does not check table/schema permissions — that is Layer 2's job.
- Does not check that the query is *meaningful* — only that it is structurally read-only.

## Layer 2 — Snowflake-side read-only role

Operational. The plugin documents (does not enforce) the recommended role. `/bigeye-config snow verify` warns if the connected role has write privileges.

```sql
CREATE ROLE DATA_READER;
GRANT USAGE ON WAREHOUSE <wh>      TO ROLE DATA_READER;
GRANT USAGE ON DATABASE <db>       TO ROLE DATA_READER;
GRANT USAGE ON ALL SCHEMAS IN ...  TO ROLE DATA_READER;
GRANT SELECT ON ALL TABLES IN ...  TO ROLE DATA_READER;
GRANT ROLE DATA_READER             TO USER <you>;
```

## Tests

See `tests/test_readonly_guard.py` + `tests/fixtures/readonly_guard_cases.json`. Run:

```bash
python tests/test_readonly_guard.py
```
