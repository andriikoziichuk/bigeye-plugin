---
name: bigeye-ticket
description: Internal — markdown ticket renderer invoked by `/bigeye-roster` action `t` or directly when explicitly typed as `/bigeye-ticket <issue>`. Do not auto-suggest.
user-invocable: true
---

# BigEye Ticket Drafter

What it does: renders a markdown ticket draft from a BigEye issue using a user-authored template at `~/.claude/bigeye-plugin/ticket-templates/<name>.md`. Output is copy-pasteable markdown — the plugin never submits anywhere.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call. Output shape lives in `skills/bigeye/references/output.md`. Template variable catalog lives in `skills/bigeye/references/improve.md` §1.

Per `preamble.md` Step 5, primary issue lookup is **unscoped** — scope applies only to MCP lineage/related calls.

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `<issue>` | Render the `default` template for the named issue | `/bigeye-ticket 10921` |
| (no arg) | Use `state.json.last_issue`; if empty, ask | `/bigeye-ticket` |
| `--template <name> <issue>` | Use a specific named template | `/bigeye-ticket --template oracle 10921` |
| `templates list` | Print name, modified-at, size for each template | |
| `templates add <name>` | Wizard: paste template body, validate, save | |
| `templates edit <name>` | Wizard: re-paste body; preserve until confirmed | |
| `templates delete <name>` | Confirm + remove file | |
| `--internal-id` | Treat the numeric argument as an internal ID (bypass MCP lookup) | |

Template-name validation: `^[a-zA-Z0-9_-]+$`. Reject `default` for `add` unless the user explicitly confirms overwrite.

Global flags — see `output.md`.

## Render path

1. Follow `preamble.md` Steps 1–7.

2. Seed templates directory on first run if `~/.claude/bigeye-plugin/ticket-templates/` is missing or empty:
   - Create the directory.
   - Copy the bundled `skills/bigeye-ticket/templates/default.md` to `~/.claude/bigeye-plugin/ticket-templates/default.md`.
   - Print: `Seeded default template. Run /bigeye-ticket templates edit default to customize, or /bigeye-ticket templates add <name> to add your own.`
   - Continue. If `--template <name>` names something other than `default`, stop with the template-not-found error.

3. Resolve the issue:
   - `--internal-id`: number is internal ID directly.
   - No arg + `state.json.last_issue` set: use it as display name. Print `Drafting for issue {display_name} (last from prior session).`
   - No arg + state empty: ask `Which issue?` and stop.
   - Display name → MCP `search_issues` (hard-fail per Step 7.B if MCP off, with workaround `Re-run with --internal-id <internal-id>`).

4. Fetch issue details via CLI:
   ```bash
   TMPDIR=$(mktemp -d -t bigeye-XXXXXX)
   trap 'rm -rf "$TMPDIR"' EXIT
   bigeye -w <profile> issues get-issues -iid <internal_id> -op "$TMPDIR"
   ```
   Read the JSON. Extract all CLI-sourced variables per `improve.md` §1 (`MCP required? = no` rows).

5. Fetch MCP-only variables (best-effort). Track an `affected_vars` list. For each:
   - `{{downstream_tables}}` — if MCP on, `mcp__bigeye__get_issue_lineage_trace` (`include_impact_analysis: true`, `max_depth: 3`). Format as bullet list. On error / MCP off: substitute `_(unavailable — MCP not configured)_` and add to `affected_vars`.
   - `{{related_issues}}` — if MCP on, `mcp__bigeye__list_related_issues`. Format as bullet list. Else: substitute and add.
   - `{{resolution_steps}}` — if MCP on, `mcp__bigeye__get_resolution_steps`. Format as numbered list. Else: substitute and add.

   Apply preamble Step 1.E filtering to MCP calls (downstream/related items kept only when in scope; primary issue itself unscoped per Step 5).

6. Render `{{sample_query}}` per `improve.md` §1.1 from the metric type.

7. Load the template body from `~/.claude/bigeye-plugin/ticket-templates/<name>.md` (default if `--template` not given). On I/O error, follow §Errors below.

8. Single-pass `{{variable}}` substitution. Variables in `improve.md` §1 → resolved values. Unknown `{{...}}` → leave literal; collect into `unknown_vars`.

9. Emit output (in this exact order):
   1. `{scope pill}`
   2. blank line
   3. Triple-backtick fenced block containing the rendered ticket body.
   4. blank line
   5. If `affected_vars` non-empty: `Note: {comma-separated names} omitted — MCP not configured (see bigeye-mcp-install.md).`
   6. If `unknown_vars` non-empty: `Warning: template referenced unknown variables: {comma-separated names}`.
   7. blank line

10. Footer:
    ```
    Next: /bigeye-rca {display_name}     (investigate before sending the ticket)
    More: /bigeye-incidents close {display_name}  ·  /bigeye-today  ·  /bigeye-ticket templates list
    ```

## Wizard flow (`templates add` / `templates edit`)

Mirror `bigeye-config init`. Ask one question at a time; show the running summary.

1. Validate `<name>` against `^[a-zA-Z0-9_-]+$`. Reject otherwise: `Template name must match ^[a-zA-Z0-9_-]+$.`
2. `add` with `<name>=default`: ask `The bundled default template already exists. Overwrite it? (y/n)` — `n` stops.
3. If file exists (both modes): print size; ask `Overwrite? (y/n)` for `add`. For `edit`, just show current size.
4. Print short variable catalog from `improve.md` §1, grouped CLI-sourced / MCP-only.
5. `Paste your template. Finish with a single line containing only EOF.`
6. Read up to 200 lines. If no `EOF` after 200, ask `Paste exceeded 200 lines without EOF terminator. Restart the wizard? (y/n)` — `n` exits without writing.
7. Scan body for `{{...}}`; categorize "used" vs "unknown" against §1. Print `Uses: <list>. Unknown placeholders: <list or "none">.`
8. Prompt `Save? (y/n)` — `n` discards.
9. Write atomically (sibling tempfile + rename).
10. Print `Wrote ~/.claude/bigeye-plugin/ticket-templates/<name>.md.`

### `templates list`

Print one row per `*.md` file:
```
| Template | Modified | Size |
|---|---|---|
| {name} | {ISO-8601 mtime} | {bytes} |
```
Empty/missing dir: `No templates yet. Run /bigeye-ticket <issue> to seed the default.`

### `templates delete <name>`

1. Confirm file exists (else list available + stop).
2. Ask `Delete template <name>? (y/n)` — `n` stops.
3. Remove file. Print `Deleted ~/.claude/bigeye-plugin/ticket-templates/<name>.md.`

## State persistence

On successful render, follow `preamble.md` Step 8.B for the `bigeye-ticket` row:
- Set `state.json.last_issue = "<display_name>"`.
- Append `{ skill: "bigeye-ticket", at: <iso8601> }` to `state.json.issues[<display>].actions`.
- Update `internal_id`, `first_seen`, `last_seen`.

Wizard subcommands (`templates add/edit/delete/list`) do **not** write state.

Then run pruning per Step 8.C.

## Errors

| Condition | Behavior |
|---|---|
| Issue not found | print error per Step 7.D; suggest checking display name |
| Template file not found | list available; suggest `/bigeye-ticket templates add <name>` |
| Template I/O error | print OS error + absolute path; do not delete |
| Unknown `{{variable}}` | leave literal; append warning per Step 9.6 |
| MCP-only variable fetch failed / MCP down | substitute `_(unavailable — MCP not configured)_`; add to `affected_vars` for footer |
| Wizard paste exceeds 200 lines | per wizard Step 6 |
| Wizard `n` confirm | discard without disk touches |
