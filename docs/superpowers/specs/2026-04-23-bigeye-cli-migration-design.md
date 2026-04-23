# Bigeye Plugin — CLI-First Rework

**Date:** 2026-04-23
**Status:** Approved design — ready for implementation planning
**Author:** Andrii Koziichuk (with Claude Code)

---

## 1. Motivation

The plugin currently routes every Bigeye operation through the `mcp__bigeye__*` MCP tools. We are moving to a CLI-first architecture where:

- **`bigeye-cli`** is the primary transport for every operation it supports
- **MCP** is retained as a second transport for operations where CLI has no equivalent, and as an optional enhancement that unlocks richer reads

Drivers:

1. **Portability.** Users should not need to run the Bigeye MCP server to get useful value from the plugin. The CLI is a single pip/pipx install and is the easier baseline.
2. **Reliability & debuggability.** CLI invocations are inspectable (the exact command is visible in the transcript, output lands in a temp directory users can open); MCP calls are opaque by comparison.
3. **Official support.** The CLI is Bigeye's officially supported interface and tracks the product.

Not drivers:

- Feature parity between CLI and MCP (the CLI is a subset; that is known and accepted)
- Performance (CLI is slower per call; we accept this)

---

## 2. Architecture overview

### 2.1 File layout after the rework

```
bigeye-plugin/
├── .claude-plugin/marketplace.json          (version bump 0.1.0 → 0.2.0)
├── README.md                                 (updated: Requirements + How it works)
├── bigeye-cli-install.md                     (unchanged)
├── bigeye-mcp-install.md                    (NEW)
├── hooks/hooks.json                         (SessionStart message updated)
├── agents/bigeye-morning-report.md          (CLI primary, MCP fallback)
├── skills/
│   ├── bigeye/
│   │   ├── SKILL.md                         (router description widened)
│   │   └── references/
│   │       ├── conventions.md               (closing-label vocab, file-output notes)
│   │       ├── scope.md                     (drop tags; pass -w profile name)
│   │       └── cli.md                      (NEW — CLI/MCP reference doc)
│   ├── bigeye-config/SKILL.md               (dual-file writes; tag migration; verify)
│   ├── bigeye-triage/SKILL.md               (CLI get-issues + post-filter)
│   ├── bigeye-rca/SKILL.md                  (CLI get-issues + MCP for lineage/related/resolution)
│   ├── bigeye-coverage/SKILL.md             (MCP for scoring; CLI for enumeration; hard-fail w/o MCP)
│   ├── bigeye-deploy/SKILL.md               (bigconfig for gaps/bulk; metric upsert for freshness/columns)
│   └── bigeye-incidents/SKILL.md            (CLI for listing/close; MCP for create_incident)
└── docs/superpowers/
    ├── specs/2026-04-23-bigeye-cli-migration-design.md  (this spec)
    └── plans/                                            (created by writing-plans next)
```

### 2.2 Two hard architectural rules

1. **CLI is the default transport for everything it supports.** The old `mcp__bigeye__*` calls appear in skills only where the CLI literally cannot do the job. Every SKILL.md is rewritten so CLI routing is the primary path and MCP is confined to clearly-marked fallback/extension steps.
2. **MCP availability is detected once per skill run, not assumed.** A single `cli.md` step wraps MCP detection (one cheap read call; on failure, set a `MCP_AVAILABLE=false` flag). Every MCP-dependent step checks the flag and degrades per the rules in §5.

### 2.3 What doesn't change

- Slash command surface and arguments (`/bigeye`, `/bigeye-triage`, `/bigeye-rca`, `/bigeye-coverage`, `/bigeye-deploy`, `/bigeye-incidents`, `/bigeye-config`)
- Scope profile concept, override flags (`--profile`, `--no-scope`, `--workspace`)
- Severity classification rules in `conventions.md`
- The chaining-suggestions pattern at the end of each skill output
- The morning report Slack template

### 2.4 What changes intentionally

- Output parsing moves from "MCP tool result in memory" to "CLI writes JSON files to `$TMPDIR`, skill reads, skill cleans up"
- Closing-label vocabulary: `METRIC_RUN_LABEL_TRUE_NEGATIVE` / `METRIC_RUN_LABEL_FALSE_POSITIVE` → CLI's `TRUE_POSITIVE` / `FALSE_POSITIVE` / `EXPECTED`
- Scope profile schema drops the `tags` field

---

## 3. The new `cli.md` reference doc

Lives at `skills/bigeye/references/cli.md`. Every skill reads it at the start of a run, same pattern as `conventions.md` and `scope.md` today.

### 3.1 Step A — Load CLI workspace binding

After `scope.md` resolves the active profile, every CLI invocation passes `-w <profile-name>`. The profile name *is* the CLI config section name (see §6 for the dual-file design).

### 3.2 Step B — Detect MCP availability

Try `mcp__bigeye__list_data_sources` with the profile's `workspace_id`. On success, set `MCP_AVAILABLE=true`. On any error, set `false` and capture the error text. Skills check the flag before every MCP call.

### 3.3 Step C — CLI invocation wrapper

Canonical pattern for read-style calls:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
bigeye -w <profile> issues get-issues \
  -wid <warehouse_id> \
  -sn <schema> \
  -op "$TMPDIR"
# parse JSON files under $TMPDIR
# cleanup: rm -rf "$TMPDIR"
```

Rules:

- Always `mktemp -d`, never a fixed path
- Always pass `-w <profile>` explicitly (even when matching `DEFAULT`) for transcript clarity
- Always `rm -rf` the tempdir at the end; skills use a trap on failure
- Timeouts: 60s single-issue reads, 180s bulk dumps, 300s `bigconfig apply`
- On non-zero exit, capture stderr and surface the exact command + error to the user
- On JSON parse failure: **do not delete the tempdir** — print the path for debugging

### 3.4 Step D — JSON output file shapes

Short table per command noting filename patterns under `-op <dir>` and the fields skills consume. Exact filenames will be verified during implementation against a real workspace and recorded as an appendix.

| Command | Files produced | Key fields |
|---|---|---|
| `issues get-issues` | one JSON per issue (by internal ID) | `id`, `displayName`, `status`, `metricConfiguration.metricType`, `dimensions[]`, `events[]`, `tableName`, `columnName`, `openedAt` |
| `metric get-info` | one JSON per metric | `id`, `metricType`, `tableName`, `columnName`, `schedule`, `recentRuns[]` |
| `catalog get-metric-info` | per-metric JSONs under warehouse/schema/table tree | same as `metric get-info` |
| `catalog get-table-info` | per-table JSONs | `id`, `schemaName`, `tableName`, `columns[]`, `metricCount` |
| `bigconfig plan` | report file + fixme files | report summary for confirmation gate |
| `bigconfig apply` | apply report | success / failure counts; created metric IDs |

### 3.5 Step E — Operation routing table

The authoritative map:

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
| Data-source listing (config wizard) | — | `list_data_sources` (required) |
| Deploy — bulk/gaps/bulk-dimension | `bigconfig plan` + `apply` | — |
| Deploy — freshness / explicit columns | `metric upsert -t SIMPLE` | — |
| Tag CRUD (`deployed-by-plugin`) | — | `list_tags` / `create_tag` / `tag_entity` (required) |
| Create / merge incident | — | `create_incident` (required) |

"Required" means: if MCP is absent, the feature is unavailable; skill prints the degradation warning and skips the dependent workflow step.

### 3.6 Step F — Degradation warning template

```
Note: MCP server unavailable — {feature_name} skipped.
  Reason: {error captured in Step B}
  To enable, see bigeye-mcp-install.md.
  {CLI-only workaround if any}
```

No emoji, per `conventions.md`.

### 3.7 Step G — Error-handling rules

- Clear CLI auth error (`401`, `Config file not found`) → stop and print: *"BigEye CLI auth not configured. Run `/bigeye-config init` or see bigeye-cli-install.md."*
- Scope error (bad warehouse ID) → print the command that ran + stderr; suggest `/bigeye-config show` to verify profile values
- JSON parse error on `-op` output → print the tempdir path (not deleted), ask user to paste the file
- Partial write success (e.g. 7 of 10 monitors created) → report success count + failed items; skip chaining suggestions

---

## 4. Per-skill rework

### 4.1 `bigeye-triage`

- **Step 0:** scope + `cli.md` Step B
- **Step 1:** `bigeye -w <profile> issues get-issues -wid/-sn <from scope> -op $TMP`; read JSON files; filter in-memory by status (`NEW`, `ACKNOWLEDGED`), `new`/`24h`/count-override args
- **Step 2:** Severity classification — unchanged, works from parsed JSON
- **Step 3:** Related issues / cluster detection — **MCP required**. If absent: print degradation warning, skip cluster counts, continue
- **Step 4:** Output — unchanged format; if clusters skipped, summary line reads *"cluster detection disabled — MCP not configured"*

### 4.2 `bigeye-rca`

- **Step 0:** scope + `cli.md` Step B
- **Step 1 (display-name → internal ID):** **MCP required**. New flag `--internal-id` lets user bypass the lookup by passing an internal ID directly
- **Step 2 (issue details):** `bigeye issues get-issues -iid <internal_id> -op $TMP`
- **Step 3 (lineage):** MCP required; graceful skip with warning if absent
- **Step 4 (related issues):** MCP required; graceful skip with warning if absent
- **Step 5 (resolution steps):** MCP required; graceful skip with warning if absent
- **Step 6 (output):** If any MCP step was skipped, prepend *"Reduced RCA — MCP unavailable"* banner after the Scope header; issue details section still renders from CLI data

### 4.3 `bigeye-coverage`

Most MCP-dependent skill. CLI provides table enumeration; dimension coverage scoring has no CLI equivalent.

- **Step 0:** scope + `cli.md` Step B
- **Steps 1–3 (coverage scoring):** MCP required. If absent: **hard-fail** with a pointer to `bigeye-mcp-install.md`. No reduced report — avoids misleading users into thinking they have coverage info they don't
- **Step 4 (history for prioritization):** `bigeye issues get-issues -wid -sn -op $TMP`, post-filter by `tableName` in JSON (no MCP needed)
- **Step 5 (output):** unchanged when MCP present

### 4.4 `bigeye-deploy`

- **Step 0:** scope + `cli.md` Step B
- **Step 1 (build plan):**
  - `gaps` / `bulk`: MCP required for coverage discovery → build a bigconfig YAML describing desired monitors
  - `freshness`: pure imperative — single table-level FRESHNESS monitor, no MCP needed
  - `columns <list>`: MCP preferred for per-column dimension inference (`get_column_dimension_coverage`). If MCP absent and `--metric-type <type>` flag was passed, use that type for all columns; otherwise hard-fail with the degradation warning suggesting either the flag or enabling MCP
- **Step 2 (present plan):** same table format; additionally show the CLI command that will run
- **Step 3 (ensure tag):** MCP required. If absent: skip tagging; warn *"Monitors will be created but not tagged — `deployed-by-plugin` tracking unavailable without MCP."*
- **Step 4 (create monitors):**
  - bigconfig path: write YAML to `$TMP/bigconfig.yaml`, run `bigconfig plan -ip $TMP -op $TMP/plan/`, show plan, on user re-confirm run `bigconfig apply -ip $TMP -auto_approve`
  - imperative path: write one YAML per metric, run `metric upsert -f <file> -t SIMPLE` per file
- **Step 5 (tag monitors):** MCP required. Query created metric IDs from the apply report; `tag_entity` per ID. Skip if MCP absent
- **Step 6 (report):** unchanged; note if tagging was skipped

Bigconfig YAML generator: template with placeholders (warehouse, schema, table, column, metric_type). Exact template documented in `cli.md` Step D appendix.

### 4.5 `bigeye-incidents`

- **Step 0:** scope + `cli.md` Step B
- **Step 1 (resolve display names → internal IDs):** MCP required; `--internal-id` flag for bypass
- **Step 2 (validate relationship):** MCP required; if absent, skip validation with a warning
- **Step 3 (generate name):** works from either CLI or MCP data — unchanged
- **Step 4 (create incident):** MCP required. If absent: hard-fail — no CLI equivalent
- **Close mode:** `bigeye issues update-issue -iid <id> -status CLOSED -cl <label>`; remap shorthand:
  - `--label true-negative` → `TRUE_POSITIVE`
  - `--label false-positive` → `FALSE_POSITIVE`
  - `--label expected` → `EXPECTED`
- **Auto mode:** CLI `get-issues` for listing; MCP fallback for clustering (same as triage); incident creation still MCP

### 4.6 `bigeye-config`

- **Wizard Step 1 (workspace):** After user enters `workspace_id`, write `[<profile>]` section to `~/.bigeye/config.ini`; run `bigeye -w <profile> configure list` to confirm reachability; on failure, print CLI error and note user may need `~/.bigeye/credentials`
- **Wizard Step 2 (data sources):** MCP required for picker. If MCP absent: prompt for warehouse IDs manually with UI-location hint
- **Wizard Step 5 (tags):** **Removed**. Print one-time notice on existing profiles with tags
- **Migration on load:** When `scope.md` Step A reads a profile with non-empty `tags`, strip in-memory, print once-per-session notice; leave on-disk file unchanged until next wizard write drops it naturally
- **Dual-file write:** Every successful wizard completion updates both `~/.claude/bigeye-plugin/profiles.json` AND `~/.bigeye/config.ini` (adds/replaces the profile's named section). Never writes `~/.bigeye/credentials`
- **New subcommand `/bigeye-config verify`:** runs a four-point health check (CLI installed, CLI workspace configured, CLI auth, MCP reachable) and prints a status table. Never exits non-zero — always shows remediation hints
- **Profile-name validation:** reject non-`[a-zA-Z0-9_-]+` names (INI-safety); reject literal `DEFAULT` unless user opts in
- **`delete <name>`:** removes `profiles.json` entry AND `~/.bigeye/config.ini` section, with explicit confirmation before touching the CLI side

### 4.7 `bigeye-morning-report` (agent)

Runs headless. CLI required; MCP optional.

- CLI for issue listing (Step 1)
- MCP-dependent steps (cluster detection, coverage check) gracefully degrade: replaced with *"Skipped — MCP not configured on this scheduled run"* in the report
- Slack summary still fires when critical issues exist, even in CLI-only mode — just without cluster/coverage stats
- Missing CLI config: agent prints existing clean error and exits (unchanged from today)

### 4.8 Router (`skills/bigeye/SKILL.md`) + hooks

- Router description: `"when BigEye MCP tools are being used"` → `"when BigEye CLI or MCP tools are being used"`
- Routing table (user intent → sub-skill): unchanged
- `hooks/hooks.json` SessionStart message:
  ```
  BigEye Data Observability plugin is active.
  CLI: required. MCP: optional (enables lineage, coverage, incidents).
  Run /bigeye-config verify to check setup, or /bigeye to get started.
  ```

---

## 5. Config files, wizard, and MCP handling

### 5.1 File ownership

| File | Plugin writes? | Plugin reads? | Role |
|---|---|---|---|
| `~/.claude/bigeye-plugin/profiles.json` | yes | yes | Per-user scope profile + default pointer |
| `~/.bigeye/config.ini` | yes (only sections it owns) | yes | CLI workspace config |
| `~/.bigeye/credentials` | **no** | existence-check only | CLI auth — user owns via `bigeye configure` |

### 5.2 Profile ↔ CLI section mapping

Plugin profile `work-area` with `workspace_id: 42`:

```ini
[work-area]
workspace_id = 42
```

Every plugin CLI call passes `-w work-area`.

### 5.3 Edge cases

| Situation | Behavior |
|---|---|
| `~/.bigeye/config.ini` missing | Wizard creates it; seeds only the new section |
| `~/.bigeye/config.ini` exists with user sections | Plugin only touches sections it creates |
| `~/.bigeye/credentials` missing | Wizard completes; prints post-wizard reminder pointing at `bigeye configure` or `bigeye-cli-install.md` |
| Profile name collides with existing CLI section | Wizard shows current contents, asks overwrite/rename |
| `~/.bigeye/` dir missing | Wizard runs `mkdir -p` |
| User passes tags field in pre-migration profile | Stripped in-memory on read; one-session notice; rewritten cleanly on next wizard write |

### 5.4 Degradation policy summary

| Feature | Without MCP |
|---|---|
| Triage issue listing | Full |
| Triage cluster counts | Skipped with warning |
| RCA issue details | Full |
| RCA display-name lookup | Hard-fail unless `--internal-id` passed |
| RCA lineage / related / resolution | Skipped with warning (each independently) |
| Coverage scoring | Hard-fail |
| Deploy bigconfig (gaps) | Hard-fail (coverage unavailable) |
| Deploy `freshness` | Works; tagging skipped with warning |
| Deploy `columns <list>` | Works only if `--metric-type` flag is passed; otherwise hard-fail (MCP needed for dimension inference). Tagging skipped |
| Incidents create | Hard-fail |
| Incidents close | Works; display-name lookup hard-fails unless `--internal-id` |
| Config wizard data-source picker | Manual warehouse-ID entry instead |
| Morning report Slack | Works; cluster/coverage sections replaced with notes |

---

## 6. New install doc: `bigeye-mcp-install.md`

Lives at repo root, mirrors `bigeye-cli-install.md` structure.

### 6.1 Outline

1. **Header + feature list** — list the plugin features MCP unlocks (RCA lineage, clustering, coverage scoring, incidents, display-name lookup, tag tracking, data-source picker)
2. **Prerequisites** — Claude Code, Bigeye API key (not CLI password — a personal access token), Python / uvx
3. **Install the MCP server** — **TBD during implementation**: verify the Bigeye MCP package's exact install recipe (uvx / pipx / PyPI name / source repo) and fill in two variants (zero-install via uvx; long-lived via pip)
4. **Register with Claude Code** — example stanza for `.mcp.json` / `claude_desktop_config.json` showing command + args + env vars (`BIGEYE_API_KEY`, `BIGEYE_WORKSPACE_ID`, `BIGEYE_BASE_URL`)
5. **Verify** — `/bigeye-config verify` flips MCP status to `[✓]`
6. **Feature matrix** — the routing table from `cli.md` Step E, user-perspective
7. **Troubleshooting** — MCP unavailable in Claude Code, 401 mismatch (API key vs CLI password), uvx cold-start costs

### 6.2 Referenced from

- `README.md` — new *"Optional: MCP server for advanced features"* section
- Every skill's MCP-absence warning prints `See bigeye-mcp-install.md`
- `/bigeye-config verify` prints the path as the fix-it hint when MCP is absent

---

## 7. Migration, rollout, versioning

### 7.1 Existing users

- `profiles.json` with no `tags`: everything just works
- `profiles.json` with `tags`: stripped in-memory, rewritten on next wizard edit; one-session notice
- Missing `profiles.json`: first skill run auto-invokes `/bigeye-config init` (unchanged from today)

### 7.2 Existing CLI users

- `~/.bigeye/config.ini` with `[DEFAULT]` or named sections: plugin leaves them alone; only touches sections it creates
- Name collision: wizard detects and asks

### 7.3 README + hooks delta

- README Requirements: CLI required, MCP optional, pointers to both install docs
- New README section: *"How it works"* — one-paragraph explanation of CLI/MCP split
- `hooks/hooks.json` SessionStart message updated (§4.8)

### 7.4 Version bump

- `.claude-plugin/marketplace.json` — `0.1.0` → `0.2.0`
- `pyproject.toml` — `0.1.0` → `0.2.0`
- Minor bump rationale: command surface unchanged; profile-schema change is soft (drops a silently-stripped field)

### 7.5 Implementation ordering

Lands in this order so intermediate states are functional:

1. `cli.md` + `bigeye-config` wizard dual-write + tag migration
2. `bigeye-triage` (proof the pattern works end-to-end)
3. `bigeye-rca` + `bigeye-incidents` (share `--internal-id` flag design)
4. `bigeye-deploy` (bigconfig YAML generator is the biggest chunk)
5. `bigeye-coverage` (minimal change; add hard-fail path)
6. `bigeye-morning-report` (reuses pieces from triage / coverage)
7. `bigeye-mcp-install.md` + README + hooks.json (docs pass; ships with or just after step 1)

Each step mergeable independently; untouched skills keep working against MCP during partial rollout.

### 7.6 Explicitly out of scope

- Python helper scripts (staying with SKILL.md + shared references)
- Output caching (each skill run does fresh CLI invocations)
- `bigeye deltas` / `collections` / `workspace` subcommands (no current skill needs them)
- Bundling our own MCP server
- Auto-upgrading the CLI for the user

---

## 8. Validation plan

Scenario-driven; no compiled tests. One checklist per skill, run once against a real workspace before shipping.

### 8.1 Per-skill scenarios

| Skill | Scenarios |
|---|---|
| `bigeye-config` | `init` on fresh machine writes both files; `init` with existing `config.ini` preserves unknown sections; `add` on existing `profiles.json` with `tags` strips and prints notice; `delete` removes both with confirmation; name with spaces rejected; `verify` correct for all four checks |
| `bigeye-triage` | Full run with MCP reachable matches current output; MCP disabled: output renders, cluster section replaced with degradation note; `new` arg filters correctly; warehouse filter narrows CLI output; empty-result phrasing correct under scope vs no-scope |
| `bigeye-rca` | Display-number + MCP: full RCA; MCP absent: hard-fail unless `--internal-id`; internal-ID + MCP absent: details render, lineage/related/resolution skipped with notes; issue-not-found gives useful error |
| `bigeye-coverage` | Full run with MCP; MCP absent: hard-fail with pointer; `dimension freshness` filter works |
| `bigeye-deploy` | `gaps` path MCP-present: YAML written, plan shown, apply creates monitors, tagged; `freshness` path: imperative upsert, tagged; `columns email,name` path MCP-present: inferred dimensions drive metric-type choice; MCP-absent on `gaps`: hard-fail; MCP-absent on `freshness`: monitor created, tagging skipped; MCP-absent on `columns` with `--metric-type COMPLETENESS`: works, tagging skipped; MCP-absent on `columns` without flag: hard-fail with pointer to flag or MCP; `edit` re-renders plan |
| `bigeye-incidents` | Display numbers + MCP creates incident; `--internal-id` + MCP absent hard-fails with pointer; `close` with MCP resolves display → internal → CLI update-issue with remapped label; `close --internal-id` MCP-absent works; `auto` mode MCP-present detects clusters |
| `bigeye-morning-report` | MCP present: full Slack; MCP absent: CLI-only report, Slack still fires on criticals, cluster/coverage replaced with notes; missing profile: clean exit |

### 8.2 Cross-cutting checks

- After a representative run, `/tmp/bigeye-*` is empty (cleanup works)
- On induced parse failure, the tempdir persists and the path is printed
- After `init` + `add` + `delete`, `~/.bigeye/config.ini` contains only plugin sections + whatever the user already had — no duplicates, no stray comments
- No emoji in skill outputs (grep non-ASCII on a full pass)
- MCP detection overhead: <1s when reachable, <3s when absent

### 8.3 MCP-absent simulation

- Sign-off test: uninstall MCP from Claude's config (most realistic)
- Day-to-day: point MCP server at an unreachable endpoint via env var override

### 8.4 Deferred

- Load / perf benchmarks (qualitative feel during validation only)
- Multi-workspace switching race conditions (single-writer assumption stands)
- CLI major-version drift (plugin targets 0.7+; `/bigeye-config verify` shows detected version)

---

## 9. Open items deferred to the implementation plan

- Exact Bigeye MCP install recipe for `bigeye-mcp-install.md` §3 (pending verification of the published MCP package)
- Exact filenames produced by each CLI command under `-op` (pending a one-time run against a real workspace to record in `cli.md` Step D appendix)
- Bigconfig YAML template shape (verify against Bigeye's current `bigconfig` schema; record in `cli.md` Step D appendix)
