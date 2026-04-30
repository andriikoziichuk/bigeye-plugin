# BigEye Plugin — Output & Formatting

Every BigEye skill MUST follow these rules for output shape. Configuration values (Slack channel, severity thresholds, deploy defaults) live in `settings.json`, not here.

---

## Status display mapping

| API status | Display |
|---|---|
| `ISSUE_STATUS_NEW` | New |
| `ISSUE_STATUS_ACKNOWLEDGED` | Ack'd |
| `ISSUE_STATUS_CLOSED` | Closed |
| `ISSUE_STATUS_MONITORING` | Monitoring |
| `ISSUE_STATUS_MERGED` | Merged |

## Priority display mapping

| API priority | Display |
|---|---|
| `ISSUE_PRIORITY_LOW` | Low |
| `ISSUE_PRIORITY_MED` | Medium |
| `ISSUE_PRIORITY_HIGH` | High |

## Severity classification

Used by skills that bucket issues. Thresholds come from `settings.json.severity`.

**Critical:**
- Freshness or Volume dimension issues (pipeline broken).
- Any issue older than `severity.critical_ack_hours` (default 4) still in NEW status.
- Any issue with `severity.critical_related_count` (default 3) or more related downstream issues.

**Warning:**
- Data quality dimension issues (Validity, Completeness, Uniqueness).
- Issues with 1–2 related downstream issues.
- Issues in ACKNOWLEDGED status older than `severity.warning_ack_hours` (default 24).

**Low:**
- Recently opened issues (< 1 hour) with no related issues.
- Distribution or Format dimension issues with no downstream impact.
- Issues already in MONITORING status.

Severity prefix in summary text: bold word — **Critical**, **Warning**, **Low**. No emoji unless the user explicitly asked.

## Closing labels

When closing issues via the CLI (`bigeye issues update-issue -cl <label>`):
- `TRUE_POSITIVE` — Real issue, now resolved.
- `FALSE_POSITIVE` — Not a real issue (noisy monitor).
- `EXPECTED` — Known exception.

User-facing shorthand to CLI mapping. Note: the `true-negative` → `TRUE_POSITIVE` mapping is intentional — kept for backward compatibility with prior plugin versions.

| Shorthand (`--label`) | CLI label |
|---|---|
| `true-negative` | `TRUE_POSITIVE` |
| `false-positive` | `FALSE_POSITIVE` |
| `expected` | `EXPECTED` |

## Tag conventions

- `deployed-by-plugin` (default; override via `settings.json.deploy.tag`): applied to all monitors created via `/bigeye-deploy`.
- Before tagging, call `mcp__bigeye__list_tags` with `search: "<tag>"`. If not found, create with `mcp__bigeye__create_tag` (`name: "<tag>"`, `color_hex: "#6366F1"`).

---

## Scope pill (line 1 of every skill)

Format: `[<profile> · <workspace_id> · <non-empty-facets>]`

Examples:
- `[my-area · 42 · 3 tables]`
- `[my-area · 42 · 3 tables · 1 source]`
- `[my-area · 42 · NO-SCOPE]`
- `[my-area · 42 · 2/3 tables]` (1 unresolved)

Rules:
- Omit facets whose count is zero.
- Single-line only; no prefix word; flush left.
- If scope has unresolved table names, append `(unresolved: "<name1>")` after the pill on the same line.
- Under `--no-scope`: render `NO-SCOPE` as the only facet (in addition to profile + workspace).

## Brief vs Full output

Every skill that renders a list of rows defaults to **Brief**: top `triage.default_brief_rows` (default 10) rows + summary. Override:
- `--full` — show all rows.
- `--limit N` — show top N rows (`N` is an integer).
- `settings.json.view.default_view = "full"` — make Full the default for every skill.

Per-invocation flags always win over the settings default.

Under Brief, after the displayed rows, when there are more rows:
```
(<N more> — add --full to see all)
```

Only print this line when there actually are more rows.

## Next / More footer

Every skill output ends with a 2-line block:

```
Next: <single best action, with the exact command inline>     (<short reason>)
More: <2-4 alternatives, · separated>
```

Examples:
- Triage: `Next: /bigeye-rca 10921     (top-scored, not yet investigated)`
- Coverage: `Next: /bigeye-deploy gaps --priority high     (3 high-priority gaps)`
- Deploy: `Next: /bigeye-triage     (verify in ~1 hour)`

Rules:
- `Next` is always a single command. Always include a parenthetical reason.
- `More` is 2–4 commands, `·` separated, no reasons. Skills pick the most likely alternates.

## Error format

Every user-facing error uses this 3-line block:

```
Error: <one-line cause>
Fix:   <exact command to run>
Why:   <one-line reason>
```

Under `--verbose`, append:

```
Details:
  command: <exact CLI that ran>
  stderr:  <full stderr>
  path:    <relevant file path>
```

When the skill has multiple parallel fixes (e.g., MCP-absent with a CLI workaround):

```
Error: <one-line cause>
Fix:   <primary command>
Fix:   <alternate command>     (<one-line condition>)
Why:   <one-line reason>
```

## Empty-result phrasing

When a scoped BigEye call returns zero items:
- If scope filters were applied: `No active issues in scope '{profile}' — all clear.`
- If `--no-scope` was used: `No active issues — all clear.`

## Picker prompt

```
Pick: [1-N], [a]ll, [q]uit
> _
```

Rules:
- Instructions on one line, prompt arrow `> _` on its own line below.
- Brackets indicate single-key shortcuts. Numbers indicate range.
- Per-skill picker rows may add tokens (e.g., `[c]lusters`, `<display_name>`, `/<slash_command>`).

## Progress indicators

Long-running multi-step skills (`bigeye-improve` heavy mode, `bigeye-deploy` bigconfig plan+apply) print numbered progress on **step transitions only**:

```
[1/4] Fetching metrics ...
[2/4] Scoring heuristics ...
[3/4] Drafting SQL bundle ...
[4/4] Waiting for paste-back
```

No spinners. Transitions only.

## Issue table column format

Used by `bigeye-triage`, `bigeye-today`, `bigeye` (dashboard), and any skill that lists issues. Standard columns:

```
 # | Issue | Score | Dim | Table | Column | Since | History
```

Variants — skills may add columns to the right (e.g., `Alerts`, `First run`) when justified, but never reorder the leading columns.

- `#` — sequential row number
- `Issue` — display name (the number shown in BigEye UI)
- `Score` — `priorityScore` (0–100 from BigEye)
- `Dim` — `metricConfiguration.dimension.displayName`
- `Table` — `metricMetadata.datasetName`, last segment only
- `Column` — `metricMetadata.fieldName`, or `—` for table-level metrics
- `Since` — human-readable time since `openedAt` (e.g., `2h`, `3d`)
- `History` — short skill tags + age from `state.json.issues[<id>].actions`, last 2 distinct skills, comma-separated. Format: `rca (4d)`, `inc (3d)`. Empty → `—`.

## Cheatsheet line conventions (dashboard / morning report)

When emitting a command list:
- One command per line, left-aligned.
- Description column starts at column 33 (single space-separated; pad as needed).
- Stable wording across runs — never reorder.

## Global flag catalog (every skill)

Documented once here; skill argument tables don't repeat the descriptions:

| Flag | Effect |
|---|---|
| `--profile <name>` | Use a specific profile for this run instead of `default_profile`. |
| `--no-scope` | Clear scope filters (workspace_id stays). |
| `--workspace <id>` | Override workspace_id for this run. |
| `--full` | Render Full instead of Brief. |
| `--limit N` | Render top N rows. |
| `--verbose` | Append the `Details:` block to error blocks. |

Skill argument tables use this 3-column shape:

```markdown
| Invocation | Purpose | Example |
|---|---|---|
| `(no arg)` | Default behavior | `/bigeye-rca` |
```
