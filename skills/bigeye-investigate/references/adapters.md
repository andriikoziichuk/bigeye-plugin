# Adapter Contracts

The engine calls four adapters. v1 implementations are the skill's tool bindings; a future Python service implements native versions of the same interfaces.

> Types referenced in adapter signatures (`IssueDetails`, `TableProfile`, `LineageGraph`, `IssueRef`, `Run`, `PackMeta`, `Pack`) are intentionally opaque in v1. v2 (Python service) defines the canonical shape. v1 implementations pass through whatever the underlying BigEye MCP / CLI / filesystem returns.

## BigeyeClient

```
resolve(issue_ref: str, internal_id_flag: bool) -> { internal_id: int, display_name: str }
get_issue(internal_id: int) -> IssueDetails
get_metric_history(internal_id: int, window: int = 30) -> list[Run]
get_table_profile(table_fq: str) -> TableProfile
get_lineage(table_fq: str, max_depth: int = 5) -> LineageGraph
get_upstream_issues(table_fq: str) -> list[IssueRef]
get_related_issues(internal_id: int, days: int = 30) -> list[IssueRef]
get_tags(entity_id: int, entity_kind: "table"|"source") -> list[str]
```

**v1 binding rules — MCP first, CLI fallback per call:**

| Method | MCP tool | CLI fallback |
|---|---|---|
| `resolve` (display→internal) | `mcp__bigeye__search_issues` | none (hard-fail if MCP down at start) |
| `get_issue` | `mcp__bigeye__get_issue` | `bigeye -w <p> issues get-issues -iid <id> -op <tmp>` |
| `get_metric_history` | `mcp__bigeye__get_issue` (events array) | same as above |
| `get_table_profile` | `mcp__bigeye__get_table_profile` | `bigeye -w <p> catalog profile -t <fq>` |
| `get_lineage` | `mcp__bigeye__get_lineage_graph` | (no fallback; degrade) |
| `get_upstream_issues` | `mcp__bigeye__list_report_upstream_issues` | (no fallback; degrade) |
| `get_related_issues` | `mcp__bigeye__list_related_issues` | (no fallback; degrade) |
| `get_tags` | `mcp__bigeye__list_entity_tags` | (no fallback; degrade) |

If MCP fails on one call and no CLI fallback exists, the adapter returns an empty result and appends an `intake_failed` TraceEvent (`{ "kind": "intake_failed", "step": "<method_name>", "stderr": "BigEye <method> unavailable; degraded" }`). The engine continues with whatever data was fetched.

> **Note:** `get_metric_history` reuses the response from the same `get_issue` MCP call; it is not a separate network round-trip.

## SnowClient

```
test_connection(profile: str) -> { ok: bool, stderr: str? }
execute(sql: str, profile: str, timeout_s: int = 60) -> { rows: list, row_count: int, ms: int, stderr: str? }
```

**v1 binding:**
- Every `execute()` MUST first call `python -m tools.readonly_guard "<sql>"`. Non-zero exit → raise `GuardError(stderr)`. Engine appends `guard_reject` trace event and does NOT call Snowflake.
- Otherwise: `snow sql -c <profile> --format json -q <sql>` via Bash with a 60s timeout. Parse JSON to `{rows, row_count}`.
- The engine caps `rows` to the first 50 rows when it writes the `query` TraceEvent's `rows_sample` field. `SnowClient.execute()` itself returns whatever Snowflake produced (subject to query LIMIT clauses); truncation is the engine's responsibility.

## PackLoader

```
list_packs() -> list[PackMeta]
load_pack(name: str) -> Pack
resolve_pack_for_tags(tags: list[str], override: str?) -> Pack    # returns _default on no match
```

**v1 binding:** filesystem read of `~/.claude/bigeye-plugin/packs/*/`. On first run, if `~/.claude/bigeye-plugin/packs/_default/` is absent, copy from `skills/bigeye-investigate/_default_pack/`. This bootstrap copy is performed by the main-thread `/bigeye-investigate` skill at startup, not inside `PackLoader` methods.

## Renderer

```
render_memo(result: InvestigationResult) -> str       # markdown
render_ticket_body(result: InvestigationResult) -> str # markdown subset
```

**v1 binding:** read `references/memo-template.md`, hydrate the derived view documented at the top of that file (joining `result` with pack lookups, trace filtering, and snow config), substitute placeholders from the hydrated view. Emits to Claude Code chat (main-thread skill).

**v2 binding (future):** Slack blocks, Jira REST payload, etc. Same input shape; different output format.
