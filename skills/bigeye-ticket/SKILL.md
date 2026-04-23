---
name: bigeye-ticket
description: Use when the user wants to draft a vendor ticket, write a Service Request, or generate a markdown report for a data vendor about a BigEye issue. Render-only — no external ticketing system writes.
user-invocable: true
---

# BigEye Ticket Drafter

Renders a markdown ticket draft from a BigEye issue using a user-authored template. Output is copy-pasteable markdown. The plugin never submits tickets anywhere.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for status/priority mapping, `skills/bigeye/references/scope.md` for scope loading, `skills/bigeye/references/cli.md` for CLI invocation and MCP-availability detection, and `skills/bigeye/references/improve.md` §1 for the template variable catalog.

## Arguments

Parse `$ARGUMENTS`. Remove `--profile`, `--no-scope`, `--workspace` scope flags first per `scope.md` Step B.

| Invocation | Behavior |
|---|---|
| `/bigeye-ticket <issue>` | Render `default` template for the named issue |
| `/bigeye-ticket --template <name> <issue>` | Use a specific named template |
| `/bigeye-ticket templates list` | Print name, modified-at, size for each template in `~/.claude/bigeye-plugin/ticket-templates/` |
| `/bigeye-ticket templates add <name>` | Wizard: paste template body, validate, save |
| `/bigeye-ticket templates edit <name>` | Wizard: re-paste body; preserve existing file until user confirms |
| `/bigeye-ticket templates delete <name>` | Confirm + remove file |
| `--internal-id` | Treat the numeric argument as an internal ID (bypass MCP display-name lookup) — required when MCP is unavailable |

Template-name validation: `^[a-zA-Z0-9_-]+$`. Reject `default` for `add` unless the user explicitly confirms overwrite.

## Render Path

### Step 0: Load scope and detect MCP

Follow `scope.md` Steps A–E then `cli.md` Step B. Per `scope.md` Step F, the primary issue lookup is **unscoped** — scope applies only to MCP lineage/related calls.

### Step 1: Seed templates directory on first run

If `~/.claude/bigeye-plugin/ticket-templates/` is missing or empty:

1. Create the directory.
2. Copy the bundled template from the plugin directory to `~/.claude/bigeye-plugin/ticket-templates/default.md`. The bundled file is at `skills/bigeye-ticket/templates/default.md` inside the plugin checkout.
3. Print exactly one line:
   `Seeded default template. Run /bigeye-ticket templates edit default to customize, or /bigeye-ticket templates add <name> to add your own.`
4. Continue with the render. If `--template <name>` names something other than `default`, stop with the "template not found" error in §Errors.

### Step 2: Resolve the issue

Parse the argument:
- If `--internal-id` was provided, treat the number as an internal ID directly; set `internal_id={number}`. Skip the MCP lookup.
- Otherwise the number is a display name; must be resolved via MCP.

**Display-name → internal-ID lookup (MCP required):**

If `MCP_AVAILABLE=true`:
  Call `mcp__bigeye__search_issues` with `name_query: "{number}"`. If no match, tell the user and stop. If multiple, list and ask which. Extract `id` (internal ID).

If `MCP_AVAILABLE=false`:
  Print the `cli.md` Step F warning with `{feature_name}=display-name lookup` and `{CLI-only workaround}=Re-run with --internal-id <internal-id> (find the internal ID in the Bigeye UI URL: app.bigeye.com/issue/<internal-id>)`. Stop the skill.

### Step 3: Fetch issue details via CLI

Use CLI per `cli.md` Step C:

```bash
TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT
bigeye -w <profile> issues get-issues -iid <internal_id> -op "$TMPDIR"
```

Read the single JSON file. Extract all CLI-sourced variables per `improve.md` §1 (the rows with `MCP required? = no`).

### Step 4: Fetch MCP-only variables (best-effort)

Track an `affected_vars` list. For each MCP-only variable:

- `{{downstream_tables}}` — if `MCP_AVAILABLE=true`, call `mcp__bigeye__get_issue_lineage_trace` with `issue_id: {internal_id}`, `include_impact_analysis: true`, `max_depth: 3`. Format the downstream nodes as a bullet list. On error or MCP unavailable: substitute `_(unavailable — MCP not configured)_` and add `{{downstream_tables}}` to `affected_vars`.
- `{{related_issues}}` — if `MCP_AVAILABLE=true`, call `mcp__bigeye__list_related_issues` with `starting_issue_id: {internal_id}`. Format as bullet list. On error or MCP unavailable: substitute and add to `affected_vars`.
- `{{resolution_steps}}` — if `MCP_AVAILABLE=true`, call `mcp__bigeye__get_resolution_steps` with `issue_id: {internal_id}`. Format as numbered list. On error or MCP unavailable: substitute and add to `affected_vars`.

Apply `scope.md` Step E filtering to the MCP calls (scope affects which downstream/related items are kept; the primary issue itself is unscoped per Step 0).

### Step 5: Render `{{sample_query}}`

Pick the skeleton from `improve.md` §1.1 based on `{{metric_type}}`. Substitute `{schema}`, `{table}`, `{column}` with the issue's values. If the metric type doesn't match a row, render the literal comment `-- no sample query available for metric type {{metric_type}}`.

### Step 6: Load the template file

Template file path: `~/.claude/bigeye-plugin/ticket-templates/<name>.md` (`<name>` defaults to `default` if `--template` not given).

On I/O error (file missing, permission denied, invalid UTF-8): follow §Errors.

### Step 7: Substitute variables

Single-pass replacement of every `{{variable}}` occurrence. Variables in `improve.md` §1 substitute with their resolved values. Any `{{...}}` not in the catalog is left literal; collect the unknowns into an `unknown_vars` list for the warning line.

### Step 8: Emit output

Print in this exact order:

1. `Scope: {per scope.md Step G}`
2. Blank line.
3. A triple-backtick fenced block containing the rendered ticket body. The fence opens with three backticks on their own line and closes with three backticks on their own line.
4. Blank line.
5. If `affected_vars` is non-empty: one line — `Note: {comma-separated {{variable}} names from affected_vars} omitted — MCP not configured (see bigeye-mcp-install.md).`
6. If `unknown_vars` is non-empty: one line — `Warning: template referenced unknown variables: {comma-separated {{variable}} names}`.
7. Blank line.
8. Suggested next: `-> Run /bigeye-rca {{issue_display_name}} if you have not already investigated.`

## Wizard Flow (`templates add <name>` / `templates edit <name>`)

Ask one question at a time. Mirror the `bigeye-config init` pattern.

1. Validate `<name>` against `^[a-zA-Z0-9_-]+$`. Reject invalid names with: `Template name must match ^[a-zA-Z0-9_-]+$.`
2. For `add` with `<name>=default`, ask: `The bundled default template already exists. Overwrite it? (y/n)` — on `n`, stop.
3. If the file exists (both modes): `A template named <name> already exists (size={size} bytes). {For edit: show current size.} {For add: ask Overwrite? (y/n)} — on n, stop.`
4. Print a short form of the variable catalog — one line per variable, grouped "CLI-sourced" vs "MCP-only", referencing `improve.md` §1 for the full list.
5. Prompt: `Paste your template. Finish with a single line containing only EOF.`
6. Read lines until `EOF`. Cap at 200 lines of body. If no `EOF` after 200 lines, stop and ask: `Paste exceeded 200 lines without EOF terminator. Restart the wizard? (y/n)` — on `n`, exit without writing.
7. Compute a usage summary by scanning the pasted body for `{{...}}` occurrences. Categorise each into "used" (in `improve.md` §1) or "unknown". Print: `Uses: {comma-separated used}. Unknown placeholders: {comma-separated unknown, or "none"}.`
8. Prompt: `Save? (y/n)` — on `n`, discard without writing.
9. On `y`, write atomically: write to a sibling temp file in the same directory, then rename over the target. This avoids partial writes if the tool is interrupted.
10. Print: `Wrote ~/.claude/bigeye-plugin/ticket-templates/<name>.md.`

### `templates list`

Read the directory. For each `*.md` file, print one row:
```
| Template | Modified | Size |
|---|---|---|
| {name} | {ISO-8601 mtime} | {bytes} |
```

If the directory is missing or empty: print `No templates yet. Run /bigeye-ticket <issue> to seed the default, or /bigeye-ticket templates add <name>.`

### `templates delete <name>`

1. Confirm file exists. On missing, print `Template <name> not found.` and list available templates.
2. Ask: `Delete template <name>? (y/n)` — on `n`, stop.
3. Remove the file. Print: `Deleted ~/.claude/bigeye-plugin/ticket-templates/<name>.md.`

## Errors

| Condition | Behavior |
|---|---|
| Issue not found (CLI or MCP `search_issues`) | Print the CLI/MCP error text; suggest re-checking the display name; stop |
| Template file not found | List available templates (names only); suggest `/bigeye-ticket templates add <name>`; stop |
| Template I/O error (permissions, encoding) | Print the OS error + absolute file path; do not delete the file; stop |
| Unknown `{{variable}}` in template | Leave placeholder literal; append the single warning line per Step 8 item 6; continue rendering |
| MCP-only variable fetch failed / MCP down | Substitute `_(unavailable — MCP not configured)_`; add to `affected_vars` for the footer note per Step 8 item 5 |
| Wizard paste exceeds 200 lines | Stop reading; ask restart per wizard Step 6; do not touch disk |
| Wizard confirm `n` | Discard in-memory template; do not touch disk |

CLI auth and scope errors: follow `cli.md` Step G unchanged.

## Output example (MCP on)

```
Scope: profile=work-area · workspace=42 · sources=1

```
Service Request Name: BigEye #10921 — Freshness on warehouse.public.orders.created_at
Product Category: [Select appropriate category]
...
SR Type: Problem/Incident
Severity: Medium
```

-> Run /bigeye-rca 10921 if you have not already investigated.
```
