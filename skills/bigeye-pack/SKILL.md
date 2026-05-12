---
name: bigeye-pack
description: Use when the user wants to create, validate, or list domain packs for /bigeye-investigate. Subcommands `new <name>`, `lint <name>`, `list`. Packs live in ~/.claude/bigeye-plugin/packs/.
user-invocable: true
---

# BigEye Pack

Scaffold and manage domain packs for `/bigeye-investigate`. A pack bundles failure-pattern knowledge for a set of BigEye-tagged tables.

Follow `skills/bigeye/references/preamble.md` Steps 1–7 before any MCP call.

## Arguments

| Invocation | Behavior |
|---|---|
| `new <name>` | Walk the user through creating a new pack; write files; run lint |
| `lint <name>` | Validate an existing pack (calls `tools/pack_lint.py`) |
| `list` | List installed packs (name, tags, priority, status) |
| (empty) | Show usage |

## Procedure — `new <name>`

1. Validate name: lowercase kebab-case (`^[a-z][a-z0-9-]*$`), not `_default`. If `~/.claude/bigeye-plugin/packs/<name>/` exists, print:
   ```
   Error: pack '<name>' already exists at <path>.
   Fix:   /bigeye-pack lint <name> to validate it, OR remove the directory first.
   ```
   Stop.

2. Ask Q1 — `One-sentence description of this pack?`

3. Ask Q2 — `BigEye tags this pack should match (comma-separated)?`
   Use `mcp__bigeye__list_tags` to autocomplete from existing tags. Accept custom values too. Require ≥1.

4. Ask Q3 — `Priority?` (multiple choice: 0 / 25 / 50 / 75; default 50). Recommend 50.

5. Ask Q4 — `Sample table this pack covers (<schema>.<table>)?` (used to validate hypothesis templates). Verify via `mcp__bigeye__search_metadata`; on no match, re-ask once, then accept anyway with a warn line.

6. Ask Q5 — `Which issue types to cover?` (multi-select; default: freshness, volume, null). Show the full list: freshness / volume / null / distribution / schema / custom.

7. For each selected issue type, ask Q6.k — `Describe one common failure pattern for {type} on {sample_table}, in one line. Press Enter to skip.` Skipping → uses the `_default` hypothesis as starter.

8. Write files:
   - `~/.claude/bigeye-plugin/packs/<name>/pack.yaml` — render `templates/pack.yaml.tmpl` with Q1-Q5 substitutions via `tools/pack_render.py`.
   - For each selected issue type:
     - `hypotheses/<type>.md` — for each Q6.k line, append a rendered `hypothesis.md.tmpl` block with `user_pattern_line` substituted. Plus one block copied from `~/.claude/bigeye-plugin/packs/_default/hypotheses/<type>.md` (first block) as a starter.
   - `verification.md` — render `templates/verification.md.tmpl`.

9. Run `python -m tools.pack_lint <pack_dir>`. Report each finding. Don't fail on warnings.

10. Print summary:
    ```
    Pack created: ~/.claude/bigeye-plugin/packs/<name>/

    Next steps:
    1. Open hypotheses/<type>.md files. Each stub has TODO markers for
       `query_template`, `expected_signal`, `playbook_link`. Fill them in.
    2. Test with: /bigeye-investigate <issue-id> --pack <name>
    3. When ready, tag tables in BigEye with one of: {tags}. The investigator
       picks the pack up automatically.

    Validate: /bigeye-pack lint <name>
    List all: /bigeye-pack list
    ```

## Procedure — `lint <name>`

Run `python -m tools.pack_lint ~/.claude/bigeye-plugin/packs/<name>`. Print stdout as-is. Exit code is propagated to the user (0 = clean, 1 = errors).

## Procedure — `list`

1. List directories under `~/.claude/bigeye-plugin/packs/`.
2. For each, parse `pack.yaml` and run `pack_lint` to get a status flag.
3. Render a table:
   ```
   Installed packs (~/.claude/bigeye-plugin/packs/):

     Name         Tags                    Priority   Covers                                  Status
     sov          sov, share-of-voice     50         freshness, volume, null, distribution   ✓
     retail-pos   pos, retail-orders      25         freshness, volume                       ⚠️ 2 stubs
     _default     —                       0          all 6 types                             ✓ (shipped)
   ```
4. Status:
   - `✓` if `pack_lint` exits 0 and zero TODO warnings
   - `⚠️ N stubs` if pack_lint warns about N TODOs
   - `✗ errors` if pack_lint exits 1

## State persistence

No state writes — read-only on `state.json`. Pack creation writes only under `~/.claude/bigeye-plugin/packs/`.

## Errors

| Condition | Block |
|---|---|
| Name invalid | `Error: pack name must be lowercase kebab-case; got '<x>'.` |
| Name is `_default` | `Error: '_default' is reserved.` |
| MCP unreachable for `list_tags` autocomplete | warn + continue (user types tags manually) |
| Pack dir already exists | see step 1 |
| Writing files fails | print the OSError + Fix line |
