---
name: bigeye-investigate
description: Use when the user wants to investigate, diagnose, or root-cause a BigEye data quality issue (by ID or URL) OR debug a data problem described in prose with optional pasted SQL — e.g. "investigate Bigeye issue 10921", "diagnose I-1234", "what's wrong with table X", "rows missing from PROD.ORDERS since monday". Dispatches the bigeye-investigator subagent and renders the resulting memo + paste-ready ticket body. Read-only on BigEye and Snowflake.
user-invocable: true
---

# BigEye Investigate

Run a pack-driven, read-only Snowflake investigation against one BigEye DQ issue. Returns a confidence-rated resolution memo with a paste-ready ticket body. Atomic. Single-issue in v1.

Follow `skills/bigeye/references/preamble.md` for scope, settings, CLI, and MCP detection before any BigEye call.

Per `preamble.md` Step 5: primary issue lookup is **unscoped**. Scope applies only to lineage expansion and related-issue filtering.

## Mode router (run first)

Classify the first positional argument:

| Pattern | Mode | Next |
|---|---|---|
| `^\d+$` or `--internal-id` set | `issue` | Resolve display name → continue at step 2 below. |
| `^https?://.*bigeye\..*/issues/\d+` | `issue` | Parse internal id from URL → continue at step 2. |
| empty AND `state.json.last_issue` set | `issue` | Resume; print `Resuming I-<display_name>.` |
| empty AND `last_freeform_investigation` set AND `last_issue` empty | `freeform` | Resume freeform; jump to Phase F3 with stored facts. |
| anything else (text, spaces, code fence) | `freeform` | Follow `references/freeform-intake.md` Phases F0–F3 first; then continue at step 4 below (skip step 2 and step 3's snow check is shared). |

## Arguments

| Invocation | Purpose | Example |
|---|---|---|
| `<display_name>` | Investigate issue by BigEye display ID | `/bigeye-investigate 10921` |
| `<url>` | Investigate from full BigEye issue URL | `/bigeye-investigate https://app.bigeye.com/issues/10921` |
| `<id> --internal-id` | Bypass display-name lookup | `/bigeye-investigate 42 --internal-id` |
| (no arg) | Resume `state.json.last_issue`; if empty, ask | `/bigeye-investigate` |
| `--pack <name>` | Force pack override | `/bigeye-investigate 10921 --pack sov` |
| `--snow <profile>` | Override stored `snow.profile` | `/bigeye-investigate 10921 --snow ro-analytics` |
| `--budget <n>` | Override pack/default budget | `/bigeye-investigate 10921 --budget 15` |
| `<prose>` | Freeform debug: describe the issue, optional fenced ```sql block | `/bigeye-investigate "PROD.ORDERS empty since monday"` |
| `--table <fq>` | Skip table clarifying question (freeform mode) | `--table PROD.ORDERS` |
| `--since <date\|interval>` | Skip filter clarifying question (freeform). ISO date or `7d`/`24h`. | `--since 7d` |
| `--type <freshness\|volume\|null\|distribution\|schema\|custom>` | Skip issue-type inference (freeform mode) | `--type volume` |
| `--ticket` | Re-emit the ticket-body block in freeform mode (memo-only by default) | `--ticket` |

Global flags from `references/output.md` apply.

## Procedure

1. Follow `preamble.md` Steps 1–7.

1.5 Route by mode (see "Mode router" above). For freeform mode: follow `references/freeform-intake.md` Phases F0–F3. On exit:
   - If F1 exhausted without `table_fq` → printed error, stop.
   - If F2 rejected → printed error, stop.
   - If F3 answered `y` → an `InvestigationRequest` with `mode: "freeform"` is built. Skip step 2 (no display-name lookup). Continue at step 3 (snow profile check).

2. Resolve issue_ref → internal_id:
   - With `--internal-id`: arg is internal_id.
   - No arg: if `state.json.last_issue` set, use it (print `Resuming I-<display_name>.`). Else ask `Which issue?` and stop.
   - Else: MCP `search_issues`. If MCP unreachable → hard-fail per `preamble.md` Step 7.B with `feature_name=display-name lookup` and Fix line `/bigeye-investigate <internal-id> --internal-id`.

3. Verify snow profile:
   - `profile = arg --snow OR profiles.json[active].snow.profile`.
   - Missing → print:
     ```
     Error: No Snowflake profile configured.
     Fix:   /bigeye-config snow set <profile>
     Why:   /bigeye-investigate requires a snow connection in profiles.json[<active>].snow.profile
     ```
     Stop.
   - Run `snow connection test -c <profile>`. Non-zero → print stderr + Fix `/bigeye-config snow verify`. Stop.

4. Build `InvestigationRequest` (request_id = fresh uuid via `python -c "import uuid; print(uuid.uuid4())"`).

5. Print one-line intent:
   ```
   Investigating I-{display_name} (pack: {pack_or_'auto'}, budget: {n}, snow: {profile}).
   Typically takes 1-3 min. Streaming progress below.
   ```

6. Spawn subagent `bigeye-investigator` with the `InvestigationRequest` as input. Subagent runs the engine and returns one JSON block matching `InvestigationResult`.

7. Validate subagent return:
   - Extract the JSON block. Validate against `references/contracts.md` shape (presence of required fields).
   - Schema-invalid → save raw to `~/.claude/bigeye-plugin/investigations/<issue_id>-<iso8601>.raw.txt`. Print:
     ```
     Error: investigator returned invalid schema.
     Raw saved: <path>
     ```
     Do NOT update `state.json.last_investigation`. Stop.

8. Render via the Renderer adapter (see `references/memo-template.md`):
   - `memo_md` = render the memo template against the result.
   - `ticket_body_md` = render the ticket template against the result.

9. Persist:
   - Write `~/.claude/bigeye-plugin/investigations/<issue_id>-<iso8601>.json` (full `InvestigationResult`).
   - Update `state.json`:
     ```
     last_issue              = <display_name>
     last_table              = <schema>.<table>
     last_workflow           = "bigeye-investigate"
     last_investigation      = { issue, request_id, at, confidence, pack_used,
                                 diagnosis_id, trace_path }
     issues[<display_name>].actions append { skill: "bigeye-investigate", at, confidence }
     ```
   - Run pruning per preamble Step 8.C.

10. Emit final block:

    ```
    {memo_md}

    ---

    ### Copy-paste ticket body
    ```markdown
    {ticket_body_md}
    ```

    Trace saved: ~/.claude/bigeye-plugin/investigations/{file}
    Next: /bigeye-roster | /bigeye-ticket {display_name}
          /bigeye-investigate {display_name} --budget {n+5} (re-run wider)
    ```

   **Freeform mode emission:** memo-only by default. If `--ticket` was set OR the diagnosis confidence is `high|medium`, also emit the ticket-body block. Otherwise omit the ```markdown ... ``` ticket block entirely. The "Next:" line in freeform mode reads:

   ```
   Next: /bigeye-investigate (resume) | /bigeye-investigate "<refined description>" (new run)
   ```

## State persistence

Per `preamble.md` Step 8.B. See step 9 above for the exact fields.

**Freeform mode writes** a separate top-level key `last_freeform_investigation` (schema in `bigeye/references/preamble.md` §8.B). The freeform run does NOT append to `issues[<display_name>].actions` and does NOT update `last_issue` / `last_table` / `last_workflow`. Trace file path: `~/.claude/bigeye-plugin/investigations/D-<short>-<iso8601>.json`.

## Errors

| Condition | Block |
|---|---|
| Display-name unresolved (MCP) | `Error: BigEye returned no match for issue '<n>'.` / `Fix: re-check the URL.` / `Why: search_issues returned 0 hits.` |
| MCP unavailable + display-name arg + no `--internal-id` | per preamble Step 7.B with workaround `/bigeye-investigate <iid> --internal-id` |
| `snow` profile unconfigured | see step 3 |
| `snow connection test` fails | see step 3 |
| Subagent returns invalid schema | see step 7 |
| Subagent timeout (no return within 5 min) | print `Error: investigator timed out after 5 min. Partial trace at <path>.` Save any partial to `<id>-<ts>.partial.json`. Do not update `last_investigation`. |
| User Ctrl-C | best-effort save of any partial trace emitted; do not update `last_investigation`. |
| Out-of-scope refusals | see `references/engine.md` Errors section |
| Freeform intake exhausts 3 rounds without `table_fq` | `Error: not enough info to investigate.` / `Fix: /bigeye-investigate "<text>" --table SCHEMA.TABLE --since 7d --type volume.` / `Why: need table, time scope, and issue type to run hypotheses.` |
| Pasted SQL fails read-only guard (main thread) | `Error: pasted SQL rejected by read-only guard: <reason>.` / `Fix: remove the write statement and re-run.` Stop. |
| Resume requested but freeform trace file deleted | Print `Note: prior freeform trace removed; starting fresh intake.` Then re-enter Phase F1 round 1. |

## Read-only invariant

Engine and subagent are read-only. The SQL guard at `tools/readonly_guard.py` enforces it before every `snow sql`. There is no override. Two-layer defense: layer 2 is the Snowflake role; see `/bigeye-config snow verify`.
