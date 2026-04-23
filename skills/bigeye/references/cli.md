# BigEye Plugin — CLI / MCP Routing

All BigEye skills MUST read this document in addition to `conventions.md` and `scope.md` before making any BigEye call. It defines:
- How to bind scope profiles to CLI workspace sections (Step A)
- How to detect MCP availability once per skill run (Step B)
- The canonical CLI invocation wrapper pattern (Step C)
- The JSON output file shapes skills consume (Step D)
- The authoritative operation routing table (Step E)
- The MCP-absence degradation warning template (Step F)
- Error-handling rules (Step G)

---

## Step A: Bind scope to CLI workspace

After `scope.md` Step B selects the active profile (say, `work-area`), every CLI invocation the skill issues MUST pass `-w work-area`. The profile name is the CLI config section name. Do this even when the profile matches the CLI's `DEFAULT` — explicit `-w` keeps transcripts self-describing.

## Step B: Detect MCP availability

Perform this exactly once per skill run, after loading scope:

1. Call `mcp__bigeye__list_data_sources` with `workspace_id: {profile's workspace_id}`.
2. On success: set `MCP_AVAILABLE=true`, discard the result.
3. On any error: set `MCP_AVAILABLE=false`, remember the error text.

Skills MUST check `MCP_AVAILABLE` before every MCP call. Do not retry MCP calls later in the same run — the result is authoritative for that run.

## Step C: CLI invocation wrapper

Use this exact pattern for any CLI call that produces output files:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> <subcommand> <subargs> -op "$TMPDIR"
# parse JSON files under $TMPDIR
```

Rules:
- Always `mktemp -d`, never a fixed path.
- Always pass `-w <profile>` (explicit even when it matches `DEFAULT`).
- Cleanup the tempdir on success. On JSON parse failure, **do not delete it** — print the path for debugging instead.
- Timeouts: 60s single-issue reads, 180s bulk dumps, 300s `bigconfig apply`.
- On non-zero exit: capture stderr and print the exact command + error to the user.

## Step D: JSON output file shapes

Each `-op <dir>` invocation produces one or more JSON files. Skills read these files, never stdout.

| Command | Files produced | Key fields |
|---|---|---|
| `issues get-issues` | one JSON per issue, named by internal ID | `id`, `displayName`, `status`, `metricConfiguration.metricType`, `dimensions[]`, `events[]`, `tableName`, `columnName`, `openedAt` |
| `metric get-info` | one JSON per metric | `id`, `metricType`, `tableName`, `columnName`, `schedule`, `recentRuns[]` |
| `catalog get-metric-info` | per-metric JSONs under warehouse/schema/table tree | same as `metric get-info` |
| `catalog get-table-info` | per-table JSONs | `id`, `schemaName`, `tableName`, `columns[]`, `metricCount` |
| `bigconfig plan` | report file + fixme files | report summary for confirmation gate |
| `bigconfig apply` | apply report | success / failure counts; created metric IDs |

Implementation note: exact filenames are workspace-dependent; skills that need specific files should enumerate via `ls "$TMPDIR"` and parse the union of JSON files.

## Step E: Operation routing table

Authoritative mapping. "Required" means MCP is needed when CLI has no equivalent — if MCP is absent, follow Step F and degrade per each skill's documented rules.

| Operation | CLI | MCP |
|---|---|---|
| List / dump issues | `issues get-issues` | — |
| Get single issue by internal ID | `issues get-issues -iid` | — |
| Resolve display-name → internal ID | — | `search_issues` (required) |
| Acknowledge / close issue | `issues update-issue` | — |
| List related issues (clustering) | — | `list_related_issues` (required) |
| Lineage trace (RCA upstream) | — | `get_issue_lineage_trace` (required) |
| Resolution steps (AI) | — | `get_resolution_steps` (required) |
| Table dimension coverage | — | `get_table_dimension_coverage` (required) |
| Column dimension coverage | — | `get_column_dimension_coverage` (required) |
| Dimension taxonomy | — | `list_dimensions` (required) |
| Table enumeration | `catalog get-table-info` | — |
| Data-source listing | — | `list_data_sources` (required) |
| Deploy — bulk / gaps | `bigconfig plan` + `apply` | — |
| Deploy — freshness / explicit columns | `metric upsert -t SIMPLE` | — |
| Tag CRUD (`deployed-by-plugin`) | — | `list_tags` / `create_tag` / `tag_entity` (required) |
| Create / merge incident | — | `create_incident` (required) |

## Step F: MCP-absence warning template

When a skill would call MCP but `MCP_AVAILABLE=false`, print exactly this block before continuing (or skipping, per the skill's rules):

```
Note: MCP server unavailable — {feature_name} skipped.
  Reason: {error captured in Step B}
  To enable, see bigeye-mcp-install.md.
  {CLI-only workaround if any}
```

No emoji. Populate `{feature_name}` from the per-skill table. `{CLI-only workaround if any}` is the skill's recommended next action (or omitted).

## Step G: Error-handling rules

- Clear CLI auth error (stderr contains `401` or `Config file not found`): stop the skill and print *"BigEye CLI auth not configured. Run `/bigeye-config init` or see bigeye-cli-install.md."*
- Scope error (bad warehouse ID — CLI returns `404` or `No such warehouse`): print the command that ran + stderr; suggest `/bigeye-config show` to verify values.
- JSON parse error on `-op` output: print the tempdir path (do not delete), ask the user to paste the file contents for diagnosis.
- Partial write success: report success count + failed items; skip chaining suggestions until fixed.

## Step H: Per-skill routing summary

| Skill | Uses CLI for | Uses MCP for | Behavior on MCP absence |
|---|---|---|---|
| `bigeye-triage` | issue listing | cluster detection | cluster section replaced with note; rest renders |
| `bigeye-rca` | issue details by ID | display-name lookup, lineage, related, resolution | display-name hard-fails unless `--internal-id`; lineage/related/resolution skipped with notes |
| `bigeye-coverage` | issue history (non-critical) | dimension coverage scoring | hard-fail with pointer |
| `bigeye-deploy` (gaps/bulk) | bigconfig plan/apply | coverage discovery, tag ops | hard-fail (coverage unavailable) |
| `bigeye-deploy` (freshness) | metric upsert | tag ops | works; tagging skipped |
| `bigeye-deploy` (columns) | metric upsert | per-column dimension inference, tag ops | works only with explicit `--metric-type` flag; tagging skipped |
| `bigeye-incidents` (close) | update-issue | display-name lookup | close works with `--internal-id`; otherwise hard-fails with pointer |
| `bigeye-incidents` (create/auto) | issue listing | create_incident, related_issues, display-name lookup | create hard-fails |
| `bigeye-morning-report` | issue listing | clustering, coverage scoring | cluster/coverage sections replaced with notes |
