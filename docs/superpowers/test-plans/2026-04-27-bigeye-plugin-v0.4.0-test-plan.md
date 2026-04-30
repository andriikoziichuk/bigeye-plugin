# BigEye Plugin v0.4.0 — Manual Test Plan

> Step-by-step verification you can run end-to-end on a live BigEye workspace. Each phase builds on the prior one — do them in order. Mark each test ✅ pass / ❌ fail / ⊘ skip as you go.

**Branch:** `feat/ux-redesign-0.4.0`
**Plan reference:** `docs/superpowers/plans/2026-04-27-bigeye-plugin-ux-redesign.md`

---

## Pre-flight checklist

Before starting, confirm:

- [ ] BigEye CLI 0.7+ installed (`bigeye --version`).
- [ ] `~/.bigeye/credentials` file exists (CLI auth).
- [ ] At least one BigEye workspace you can hit.
- [ ] **MCP**: Bigeye MCP server is configured AND reachable (Phase 3 / 6 / 7 / 10 require it; Phase 4 explicitly tests with MCP off).
- [ ] **Slack MCP**: configured ONLY if you plan to run Phase 10 (morning agent posts to Slack).
- [ ] Workspace has at least: 5 open issues, 1 closed-in-last-7-days issue, 2-3 tables you own. If you don't have all that, some assertions will be light.
- [ ] You have the v0.4.0 changes either staged or merged. The repo path is `/Users/andriik-mbp/PycharmProjects/bigeye-plugin/`.
- [ ] Plugin installed in Claude Code: `/plugin install bigeye-plugin@andriikoziichuk-bigeye-plugin`.

**Capture pre-state for the upgrade notice test (Phase 11):**

```bash
mkdir -p /tmp/bigeye-test-backup
cp -a ~/.claude/bigeye-plugin /tmp/bigeye-test-backup/ 2>/dev/null || true
cp -a ~/.bigeye /tmp/bigeye-test-backup/ 2>/dev/null || true
ls -la ~/.claude/bigeye-plugin/ 2>/dev/null
```

You'll restore from this backup in Phase 11 to re-trigger the upgrade notice.

---

## Phase 1 — Setup & sanity

### 1.1 Profiles config exists OR `init` creates one

Run:

```
/bigeye-config show
```

**Pass if:** prints active profile + table of profiles, OR (if `profiles.json` is missing) prints `No BigEye profiles configured yet. Run /bigeye-config init to set one up.`

If you don't have a profile yet, run `/bigeye-config init` and walk through the wizard. When it asks for `workspace_id`, use a real one. Skip the data source / table / schema filter prompts (`n`) for the first run unless you want to test those too.

**Pass if:** wizard writes `~/.claude/bigeye-plugin/profiles.json` and the matching `[<profile>]` section in `~/.bigeye/config.ini`. Print confirmation appears.

---

### 1.2 First skill run seeds settings.json

If `~/.claude/bigeye-plugin/settings.json` already exists, delete it first:

```bash
rm -f ~/.claude/bigeye-plugin/settings.json
```

Then run any skill that loads preamble. Pick a cheap one:

```
/bigeye-config show
```

**Pass if:** the output begins with one line `Wrote ~/.claude/bigeye-plugin/settings.json with defaults — edit via /bigeye-config settings.` (this only appears on first encounter — see Phase 11 for upgrade-notice details).

```bash
cat ~/.claude/bigeye-plugin/settings.json
```

**Pass if:** the file contains all of these top-level keys: `_meta`, `slack`, `severity`, `triage`, `deploy`, `view`. The defaults match the schema in `skills/bigeye/references/preamble.md` Step 2.

---

### 1.3 `/bigeye-config verify`

```
/bigeye-config verify
```

**Pass if:** prints a 5-row status table with `[a]` CLI installed, `[b]` CLI workspace configured, `[c]` CLI auth, `[d]` MCP server reachable, `[e]` Settings file. The 5th row should now read `present` (since 1.2 just wrote the file).

---

## Phase 2 — Settings management

### 2.1 `settings show`

```
/bigeye-config settings show
```

**Pass if:** prints the merged JSON pretty-printed with 2-space indent, key order `_meta, slack, severity, triage, deploy, view` (canonical). Below the JSON, prints the line `Edit any key with: /bigeye-config settings edit <dotted.key> <value>`.

---

### 2.2 `settings edit` — string

```
/bigeye-config settings edit slack.channel '#test-data-quality'
```

**Pass if:** prints `Updated slack.channel: #data-quality-alerts -> #test-data-quality` and `Wrote ~/.claude/bigeye-plugin/settings.json.`

Then verify:
```bash
grep test-data-quality ~/.claude/bigeye-plugin/settings.json
```
**Pass if:** the new value is present in the file.

Restore default for later phases:
```
/bigeye-config settings edit slack.channel '#data-quality-alerts'
```

---

### 2.3 `settings edit` — boolean

```
/bigeye-config settings edit slack.critical_only false
```

**Pass if:** prints `Updated slack.critical_only: True -> False` (or similar). Re-set to `true` after.

---

### 2.4 `settings edit` — integer

```
/bigeye-config settings edit triage.max_issues 25
```

**Pass if:** prints `Updated triage.max_issues: 50 -> 25`. Re-set to `50` after.

---

### 2.5 `settings edit` — invalid key (top-level only)

```
/bigeye-config settings edit slack '#oops'
```

**Pass if:** prints the `Error / Fix / Why` block:
```
Error: invalid settings key 'slack'.
Fix:   /bigeye-config settings show     (lists valid keys)
Why:   Keys must be dotted paths (e.g., slack.channel, view.default_view).
```

---

### 2.6 `settings edit` — non-existent leaf key

```
/bigeye-config settings edit slack.nonexistent_key 'x'
```

**Pass if:** prints an `Error / Fix / Why` block stating the parent path or leaf is unknown — should refuse to create new keys.

---

### 2.7 `settings edit` — `_meta.upgrade_seen` is protected

```
/bigeye-config settings edit _meta.upgrade_seen false
```

**Pass if:** prints exactly:
```
Error: _meta.upgrade_seen is managed by the plugin.
Fix:   (no action needed)
Why:   This flag flips automatically on first run after upgrade.
```

The flag is NOT changed (verify with `cat ~/.claude/bigeye-plugin/settings.json | grep upgrade_seen`).

---

## Phase 3 — Atomic skills with MCP ON

Confirm MCP is reachable before starting:

```
/bigeye-config verify
```

The `[d]` row should be `[✓]`. If not, configure MCP per `bigeye-mcp-install.md` and re-test.

---

### 3.1 `/bigeye-triage` — default (all open issues)

```
/bigeye-triage
```

**Pass if all of:**
- Line 1 is a scope pill in the format `[<profile> · <workspace_id> · <facets>]`.
- Heading `## BigEye Triage — <date>`.
- Sections `### New (N)`, `### Ack'd (N)`, `### Monitoring (N)` (sections with 0 issues are omitted).
- Each section's table has columns: `# | Issue | Score | Dim | Table | Column | Since | History`.
- `Summary:` line counts `new · ack'd · monitoring · clusters`.
- `Next:` and `More:` footer at the bottom.

**Inspect:** if there's a `History` column populated, that confirms `state.json` integration with prior sessions. Empty state means `—`.

---

### 3.2 `/bigeye-triage new` — only NEW status

```
/bigeye-triage new
```

**Pass if:** only the `### New (N)` section appears. Sections for Ack'd / Monitoring are absent.

---

### 3.3 `/bigeye-triage 24h`

```
/bigeye-triage 24h
```

**Pass if:** only issues opened in the last 24 hours are listed. Otherwise format is identical to 3.1.

---

### 3.4 `/bigeye-triage --full`

```
/bigeye-triage --full
```

**Pass if:** the truncation marker `(N more — add --full to see all)` does NOT appear. All issues in scope are listed.

---

### 3.5 `/bigeye-rca <known-issue>`

Pick a real display name from the 3.1 output (e.g., `10921`):

```
/bigeye-rca 10921
```

**Pass if all of:**
- Scope pill on line 1.
- `## Root Cause Analysis — Issue #10921`.
- Sections: Issue, Lineage Trace, Related Issues, Resolution Steps, Suggested Actions.
- `Next:` and `More:` footer.

**Bonus check:**
```bash
grep -A2 '"last_issue"' ~/.claude/bigeye-plugin/state.json
grep -A20 '"10921"' ~/.claude/bigeye-plugin/state.json
```

**Pass if:** `state.json.last_issue == "10921"` and `state.json.issues["10921"].actions[-1].skill == "bigeye-rca"`.

---

### 3.6 `/bigeye-rca` — no-arg fallback

```
/bigeye-rca
```

**Pass if:** prints one line `Resuming issue 10921 from previous session.` (using the issue from 3.5), then runs the full RCA again.

---

### 3.7 `/bigeye-coverage <table>`

Pick a real table from your scope (e.g., `orders`):

```
/bigeye-coverage orders
```

**Pass if all of:**
- Scope pill on line 1.
- `## Coverage Report — <schema>.orders`.
- `### Overall Score: N% (covered/total)`.
- `### Table-Level Coverage` table with `Dimension | Category | Status | Monitor` columns.
- `### Top Column Gaps (prioritized)` table with `Column | Missing Dimensions | Past Issues (30d) | Priority`.
- (Optional) `### Improvable Monitors (N)` if any cheap-heuristic flags fire.
- `### Suggested Monitor Deployment` with deploy hints.
- `Next:` / `More:` footer.

**Bonus check:**
```bash
grep -A3 '"last_table"' ~/.claude/bigeye-plugin/state.json
```

**Pass if:** `last_table` is set to the fq table name and an action entry was appended.

---

### 3.8 `/bigeye-coverage` — no-arg fallback

```
/bigeye-coverage
```

**Pass if:** prints `Coverage on <fq> (last table from prior session).` and runs the same coverage analysis.

---

### 3.9 `/bigeye-improve <table> --light`

```
/bigeye-improve orders --light
```

**Pass if all of:**
- Scope pill on line 1.
- `## Monitor Improvement Report — <schema>.orders`.
- (May have) `### Weak Monitors (N)`, `### Coverage Suggestions (N)`, `### Deploy hints` sections.
- NO SQL bundle (because `--light`).
- NO paste-back protocol.
- `Next:` / `More:` footer.

---

### 3.10 `/bigeye-improve <table> --sql-only`

```
/bigeye-improve orders --sql-only
```

**Pass if:** prints the primary report PLUS a SQL bundle with `-- query N: <purpose>` headers, but does NOT print the `--- BEGIN RESULTS ---` paste-back delimiter. Stops cleanly.

---

### 3.11 `/bigeye-improve` — no-arg fallback

```
/bigeye-improve
```

**Pass if:** prints `Improving <fq> (last table from prior session).` (using the table from 3.7/3.9), then runs heavy mode by default.

If you want to test the heavy-mode paste loop, follow the SQL bundle through to completion:
1. Copy the queries.
2. Run them in your warehouse.
3. Paste results in your next message under `--- BEGIN RESULTS ---`.

**Pass if:** plugin parses the results and emits `## Refined Recommendations` + updated `Deploy hints`.

If you don't want to do that, send `cancel` instead.

**Pass if:** prints best-effort report from prior steps + `Deep refinement cancelled — Refined Recommendations section omitted.`

---

### 3.12 `/bigeye-incidents auto`

```
/bigeye-incidents auto
```

**Pass if all of:**
- Scope pill on line 1.
- `## Auto-Detected Issue Clusters`.
- One `### Cluster N: ...` per detected cluster, with the issue table.
- (If no clusters) `No issue clusters detected.` or similar empty-result phrasing.
- Picker prompt `Create incidents for these clusters? (all/1,2/none)`.

You can answer `none` to skip the actual create.

---

### 3.13 `/bigeye-incidents close <issue> --label expected`

⚠️ **This writes to BigEye.** Pick a *throwaway* test issue (or one you know is expected/false-positive) before running.

```
/bigeye-incidents close 10921 --label expected
```

**Pass if:** prints `Issue #10921 closed with label EXPECTED.` and the footer.

**Bonus check:**
```bash
grep -A2 '"10921"' ~/.claude/bigeye-plugin/state.json
```

**Pass if:** `state.json.issues["10921"].status_when_last_seen == "CLOSED"` and `actions[-1].note == "closed with EXPECTED"` (or similar).

---

### 3.14 `/bigeye-ticket <issue>`

```
/bigeye-ticket 10923
```

(Use a different open issue.)

**Pass if all of:**
- Scope pill on line 1.
- A triple-backtick fenced block with the rendered ticket body.
- All `{{...}}` placeholders are substituted. Any unsubstituted ones print a warning line.
- If MCP fetches partially failed (rare), a `Note: ... omitted — MCP not configured` footer appears.
- `Next:` / `More:` footer.

**Bonus check:**
```bash
grep -A2 '"10923"' ~/.claude/bigeye-plugin/state.json
```

**Pass if:** `last_issue == "10923"` and `bigeye-ticket` action appended.

---

## Phase 4 — Atomic skills with MCP OFF

Disable the BigEye MCP server. Easiest way: edit your Claude Code MCP config to comment out the `bigeye` server entry, OR run on a host without it. Verify:

```
/bigeye-config verify
```

The `[d]` MCP row should now be `[!]` or `[✗]`.

---

### 4.1 `/bigeye-triage` — graceful degradation

```
/bigeye-triage
```

**Pass if all of:**
- Triage table still renders (CLI does the issue dump).
- Cluster section is replaced with a one-line `Error: MCP server unavailable — cluster detection skipped. Fix: ... Why: ...` block OR a `Cluster detection: unavailable` summary line.
- `History` column is `—` for issues with no prior state.json activity (state.json itself works regardless of MCP).
- Footer still prints.

---

### 4.2 `/bigeye-rca <display>` — hard-fails with workaround

```
/bigeye-rca 10921
```

**Pass if:** prints the `Error / Fix / Why` block with `feature_name=display-name lookup`. Fix line says `/bigeye-rca <internal-id> --internal-id`.

---

### 4.3 `/bigeye-rca <internal-id> --internal-id` — works MCP-off

You'll need an internal ID. Find one by reading `~/.claude/bigeye-plugin/state.json` for an `internal_id` field, OR from the BigEye UI URL `app.bigeye.com/issue/<internal-id>`.

```
/bigeye-rca 42 --internal-id
```

**Pass if all of:**
- A line `Reduced RCA — MCP unavailable. Lineage, related issues, and/or resolution steps omitted. See bigeye-mcp-install.md.` appears after the scope pill.
- Issue section renders (CLI works).
- Lineage Trace, Related Issues, Resolution Steps sections each contain `(skipped — MCP unavailable)`.
- `Next:` / `More:` footer.

---

### 4.4 `/bigeye-coverage <table>` — hard-fails

```
/bigeye-coverage orders
```

**Pass if:** prints the `Error / Fix / Why` block with `feature_name=dimension coverage scoring`. The skill stops without rendering a coverage report (no CLI equivalent).

---

### 4.5 `/bigeye-improve <table> --light` — partial degradation

```
/bigeye-improve orders --light
```

**Pass if all of:**
- The MCP-absent warning prints once (for `feature_name=missing-coverage suggestions`).
- `### Weak Monitors (N)` section still renders (config heuristics use CLI data only).
- `### Coverage Suggestions` section is absent or empty (skipped).
- No SQL bundle.

---

### 4.6 `/bigeye-incidents auto` — hard-fails

```
/bigeye-incidents auto
```

**Pass if:** the `Error / Fix / Why` block appears with `feature_name=cluster auto-detection`. Skill stops.

---

### 4.7 `/bigeye-ticket --internal-id <internal-id>` — partial degradation

```
/bigeye-ticket 42 --internal-id
```

**Pass if all of:**
- Render succeeds.
- `{{downstream_tables}}`, `{{related_issues}}`, `{{resolution_steps}}` are each substituted with `_(unavailable — MCP not configured)_`.
- A footer note `Note: {{downstream_tables}}, {{related_issues}}, {{resolution_steps}} omitted — MCP not configured (see bigeye-mcp-install.md).` appears.

---

**Re-enable MCP** before continuing. Verify with `/bigeye-config verify`.

---

## Phase 5 — `state.json` writes & no-arg fallbacks

### 5.1 state.json structure

```bash
python3 -m json.tool ~/.claude/bigeye-plugin/state.json | head -60
```

**Pass if:** valid JSON. Top-level keys: `_meta`, `last_issue`, `last_table`, `last_workflow`, `issues`, `tables`. Each issue and table entry has `first_seen`, `last_seen`, `actions[]`.

---

### 5.2 `last_issue` resume

After running 3.5 (which set `last_issue=10921`):

```
/bigeye-rca
```

**Pass if:** prints `Resuming issue 10921 from previous session.` (already verified in 3.6 — re-run if state was disturbed).

---

### 5.3 `last_table` resume

```
/bigeye-coverage
```

**Pass if:** prints `Coverage on <last_table> (last table from prior session).`

---

### 5.4 LRU pruning at 500 issues / 100 tables caps

⚠️ This requires a small Python helper. Skip if you'd rather not.

```bash
python3 - <<'PY'
import json, os
p = os.path.expanduser("~/.claude/bigeye-plugin/state.json")
with open(p) as f:
    s = json.load(f)
# inject 600 fake issues with old timestamps
for i in range(600):
    s["issues"][f"FAKE_{i:04d}"] = {
        "internal_id": 99000 + i,
        "display_name": f"FAKE_{i:04d}",
        "first_seen": "2020-01-01T00:00:00Z",
        "last_seen": "2020-01-01T00:00:00Z",
        "status_when_last_seen": "ACKNOWLEDGED",
        "actions": [],
    }
with open(p + ".tmp", "w") as f:
    json.dump(s, f, indent=2)
os.rename(p + ".tmp", p)
print(f"Injected. Issues count now: {len(s['issues'])}")
PY
```

Then run any skill that writes state (e.g., `/bigeye-rca 10921 --internal-id` if MCP is off, or `/bigeye-rca 10921` with MCP on).

```bash
python3 -c "import json,os; s=json.load(open(os.path.expanduser('~/.claude/bigeye-plugin/state.json'))); print('issues:', len(s['issues']))"
```

**Pass if:** the count is ≤ 500. The oldest `FAKE_*` entries (with `last_seen` of 2020) should be gone; the real new entry (10921) should be present.

---

## Phase 6 — Dashboard

### 6.1 `/bigeye` — default render

```
/bigeye
```

**Pass if all of:**
- Line 1: scope pill.
- `## BigEye Dashboard — <weekday> <month> <day>, <HH:MM>`.
- `Status:` line with open / NEW / clusters / coverage counts.
- `Last:` line referencing real activity from state.json (or empty fallback).
- `Open issues (top 5 by score):` table with up to 5 rows + truncation marker if there are more.
- (Maybe) `Recently closed (last 7 days):` section with up to 5 lines (only if there are entries).
- `Your tables:` section with coverage / open / last-action per table.
- `Commands:` cheatsheet — exactly 10 lines, stable order.
- `Next:` / `More:` footer.

---

### 6.2 `/bigeye --all`

```
/bigeye --all
```

**Pass if:** scope pill changes to reflect no scope filtering (e.g., `NO-SCOPE` or wider counts). Issue list and tables sections expand.

---

### 6.3 `/bigeye <unknown args>` — "Did you mean" hint

```
/bigeye triage
```

**Pass if:** the FIRST line printed is `Did you mean /bigeye-<x> <args>? /bigeye shows the dashboard; individual commands run tasks.`. Then the dashboard renders normally below.

---

### 6.4 `/bigeye` with empty state.json

```bash
mv ~/.claude/bigeye-plugin/state.json /tmp/state.json.bak
```

```
/bigeye
```

**Pass if:** the `Last:` line reads `Last: no activity yet — run /bigeye-today to get started`. Dashboard otherwise renders normally.

```bash
mv /tmp/state.json.bak ~/.claude/bigeye-plugin/state.json
```

---

### 6.5 `/bigeye` shows recently closed (after 3.13)

If you ran 3.13 with a real close, then:

```
/bigeye
```

**Pass if:** `Recently closed (last 7 days):` section appears with at least the issue closed in 3.13 (e.g., `#10921 ... (expected, ... ago)`).

---

## Phase 7 — Workflows

### 7.1 `/bigeye-today` — full reactive loop

```
/bigeye-today
```

**Turn 1 pass if:**
- Scope pill on line 1.
- `## Today — N open · N New · N Ack'd · N Monitoring · N clusters`.
- Issue table.
- Picker prompt: `Pick: [1-N], [a]ll critical, [c]lusters, <display_name>, /<slash_command>, [q]uit`.
- `> _` on its own line below.

Type `1` (or any row number).

**Turn 3 (action menu) pass if:**
- `## Issue <display> — <dimension> on <schema>.<table>`.
- `Since: ... · Priority: ... · Alerts: ...`.
- `History (local): ...` line.
- 6 menu options [1] Root-cause, [2] Close, [3] Group, [4] Ticket, [5] Back, [q] Quit.

Type `1` (Root-cause analysis).

**Pass if:** `/bigeye-rca <display>` runs, then on completion the action menu re-renders.

Type `5` (Back to issue list). Should re-render Turn 1.

Type `q`. **Pass if:** prints `Session: N actions · ...` summary then footer.

---

### 7.2 `/bigeye-today --report-only`

```
/bigeye-today --report-only
```

**Pass if:** prints Turn 1 (scope pill, heading, issue table) + footer. NO picker prompt. Skill exits.

---

### 7.3 `/bigeye-today` picker `a` (all critical)

```
/bigeye-today
```

At the picker, type `a`.

**Pass if:** the workflow iterates through Critical-severity issues (per `output.md` rules), running RCA for each. After the last, returns to Turn 1.

(This may take a while if you have many criticals. Type `q` to bail out partway.)

---

### 7.4 `/bigeye-today` picker `c` (clusters)

If you have clusters detected:

```
/bigeye-today
```

At the picker, type `c`.

**Pass if:** prints `## Clusters` with `### Cluster N: (count) — auto_name` entries. Picker `Pick a cluster number, or [b]ack:`.

Type a cluster number. **Pass if:** confirms `Create incident for N issues? (y/n)`. Answer `n` to skip the actual write.

If MCP is off and you type `c`: **pass if** prints `Cluster detection unavailable — MCP not configured.` and stays in the main picker.

---

### 7.5 `/bigeye-today` exit via slash command

```
/bigeye-today
```

At any picker, type `/bigeye-rca 10925`.

**Pass if:** the workflow exits and `/bigeye-rca 10925` runs as a fresh atomic skill (no return to the today loop).

---

### 7.6 `/bigeye-table <name>`

```
/bigeye-table orders
```

**Turn 1 pass if:**
- Scope pill on line 1.
- `## Table — <schema>.orders`.
- `Coverage: N% · N monitors · N open issues · last deploy: ... (Nd ago)`.
- `Open issues on this table:` table.
- 6 menu options [1] Coverage report, [2] Improve monitors, [3] Deploy gaps, [4] Open issue, [5] Switch table, [q] Quit.
- Picker `Pick: [1-5], [q]uit`.

Type `1`. **Pass if:** `/bigeye-coverage orders` runs, then on return Turn 1 re-renders.

Type `5`, then enter a different table name. **Pass if:** Turn 1 re-renders for the new table.

Type `q`. **Pass if:** session summary + footer.

---

### 7.7 `/bigeye-table` — no-arg uses last_table

```
/bigeye-table
```

**Pass if:** prints `Table <fq> (last from prior session).` and renders Turn 1 for that table.

---

### 7.8 `/bigeye-table` — empty state shows top-5 picker

```bash
mv ~/.claude/bigeye-plugin/state.json /tmp/state.json.bak
```

```
/bigeye-table
```

**Pass if:** if you have enough table activity (you don't, since state was wiped), the recent-tables picker appears. If not, the skill should ask `Which table?` and stop.

```bash
mv /tmp/state.json.bak ~/.claude/bigeye-plugin/state.json
```

---

### 7.9 `/bigeye-table <bare-name>` with MCP off

Disable MCP first.

```
/bigeye-table orders
```

**Pass if:** prints the `Error / Fix / Why` block with `feature_name=table-name resolution`. Fix line says `/bigeye-table <source>.<schema>.<table>`. Skill stops.

Then with the qualified form:

```
/bigeye-table warehouse.public.orders
```

**Pass if:** Turn 1 renders, but the Coverage cell shows `—` (because MCP coverage is unavailable).

Re-enable MCP.

---

## Phase 8 — Output shape

These are spot-checks across multiple skills.

### 8.1 Scope pill on every skill

Run any 3 skills (e.g., `/bigeye-triage`, `/bigeye-rca <id>`, `/bigeye`).

**Pass if:** Line 1 of EACH output matches the format `[<profile> · <workspace_id> · <facets>]`. Facets with count 0 are omitted. No facet appears with the prefix word `Scope:` (the old format).

---

### 8.2 Brief default + truncation marker

Ensure your scope has more than 10 issues. Run:

```
/bigeye-triage
```

**Pass if:** each status section shows up to 10 rows + the line `(N more — add --full to see all)` if there are more.

---

### 8.3 `--full` and `--limit N`

```
/bigeye-triage --full
```

**Pass if:** truncation marker is absent; all rows shown.

```
/bigeye-triage --limit 3
```

**Pass if:** at most 3 rows per status section. Truncation marker `(N more — add --full to see all)` appears if there were more.

---

### 8.4 `view.default_view = "full"` override

```
/bigeye-config settings edit view.default_view full
/bigeye-triage
```

**Pass if:** all rows shown without `--full` (Brief default has been overridden globally).

Restore default:
```
/bigeye-config settings edit view.default_view brief
```

---

### 8.5 Next/More footer everywhere

For any 3 skill outputs, confirm the last 2 non-blank lines are:

```
Next: <one-command-with-args>     (<reason>)
More: <2-4 commands separated by ·>
```

---

### 8.6 Error/Fix/Why block

Trigger an error deliberately. Easy way: misspell a profile name.

```
/bigeye-triage --profile nonexistent-profile-xyz
```

**Pass if:** prints
```
Profile `nonexistent-profile-xyz` not found. Available profiles: {list}.
```
or an `Error / Fix / Why` 3-line block. Either matches the spec. Confirm there's no stack trace.

---

## Phase 9 — Scope flags

### 9.1 `--profile <name>`

If you have multiple profiles, run any skill with `--profile <other-name>`. **Pass if:** the scope pill reflects the other profile.

---

### 9.2 `--no-scope`

```
/bigeye-triage --no-scope
```

**Pass if:** scope pill shows `NO-SCOPE`. Issue counts may be larger than the default-scoped run.

---

### 9.3 `--workspace <id>`

```
/bigeye-triage --workspace <real-workspace-id>
```

**Pass if:** scope pill shows the new `workspace_id`; results reflect that workspace.

---

## Phase 10 — Morning agent

### 10.1 Manual run

```
/bigeye-morning-report
```

(Or, if you have it scheduled, wait for the cron to fire and inspect the output.)

**Pass if:**
- Output starts with the scope pill.
- `## Morning Report — <date> <time>`.
- `### Current State` section contains the same shape as `/bigeye-today --report-only` (issue table, summary).
- `### Coverage` section.
- `### Action Items` numbered list with conditional bullets.

---

### 10.2 Slack post (only if Slack MCP is configured)

⚠️ This actually posts to Slack. Edit your channel to a safe test channel first:

```
/bigeye-config settings edit slack.channel '#test-bigeye-alerts'
```

```
/bigeye-morning-report
```

**Pass if:** the Slack post appears in the test channel with the morning-report template body. If `critical_only=true` and there are no Critical issues, NO post is made.

Restore your real channel after.

---

### 10.3 `critical_only=true` with zero criticals — silent

If your scope has zero Critical issues right now, the agent should NOT post to Slack (with `slack.critical_only=true`).

If you have criticals, temporarily flip `critical_only` to false and re-run for the post path; flip back to true after.

---

## Phase 11 — Upgrade notice

The upgrade notice fires exactly once per upgrade. To re-test it, flip the flag back.

**Method 1 (simulate fresh upgrade):**

```bash
# stop reading the file (no skills running)
# manually flip the flag
python3 -c "
import json, os
p = os.path.expanduser('~/.claude/bigeye-plugin/settings.json')
with open(p) as f: s = json.load(f)
s['_meta']['upgrade_seen'] = False
with open(p + '.tmp', 'w') as f: json.dump(s, f, indent=2)
os.rename(p + '.tmp', p)
print('upgrade_seen reset to false')
"
```

Then run any skill:

```
/bigeye-config show
```

**Pass if:** the FIRST output (after preamble setup) is the line:
```
Upgraded to bigeye-plugin 0.4.0. New: /bigeye (dashboard), /bigeye-today, /bigeye-table.
Your profiles and templates are preserved. See README or run /bigeye for a tour.
```

Then run another skill:

```
/bigeye-config show
```

**Pass if:** the upgrade notice does NOT appear (it printed once, the flag flipped to true).

```bash
grep upgrade_seen ~/.claude/bigeye-plugin/settings.json
```

**Pass if:** `"upgrade_seen": true`.

---

## Phase 12 — Migration & regression

### 12.1 `profiles.json` schema unchanged

```bash
python3 -m json.tool ~/.claude/bigeye-plugin/profiles.json
```

**Pass if:** valid JSON; no `tags` field is required (the old optional field can still be present — it gets stripped on read with a one-line notice).

---

### 12.2 Ticket templates still work

```
/bigeye-ticket templates list
```

**Pass if:** prints the list of `*.md` files in `~/.claude/bigeye-plugin/ticket-templates/`. The `default.md` should be present.

```
/bigeye-ticket --template default 10923
```

**Pass if:** renders successfully (any user-authored templates from before the upgrade also work).

---

### 12.3 No skill references the deleted reference files

```bash
grep -rn "skills/bigeye/references/scope.md\|skills/bigeye/references/cli.md\|skills/bigeye/references/conventions.md" skills/ agents/ README.md
```

**Pass if:** zero matches. The 3 deleted reference files have no live references in skill bodies, agents, or the README.

---

### 12.4 Both manifests at 0.4.0

```bash
grep '"version"' .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

**Pass if:** both files print `"version": "0.4.0"`.

---

## Cleanup

Restore your original Slack channel + any other settings you changed during testing:

```
/bigeye-config settings edit slack.channel '#data-quality-alerts'
/bigeye-config settings edit slack.critical_only true
/bigeye-config settings edit triage.max_issues 50
/bigeye-config settings edit view.default_view brief
```

If you injected fake state.json entries in 5.4 and they got pruned, your real entries should still be there. If anything looks wrong, restore from the pre-flight backup:

```bash
rm -rf ~/.claude/bigeye-plugin
cp -a /tmp/bigeye-test-backup/bigeye-plugin ~/.claude/bigeye-plugin
```

---

## Summary scorecard

| Phase | Title | Tests | Critical? |
|---|---|---|---|
| 1 | Setup & sanity | 3 | yes |
| 2 | Settings management | 7 | yes |
| 3 | Atomic skills (MCP on) | 14 | yes |
| 4 | Atomic skills (MCP off) | 7 | yes if you ship MCP-optional support |
| 5 | state.json + no-arg fallbacks | 4 | yes |
| 6 | Dashboard | 5 | yes |
| 7 | Workflows (today + table) | 9 | yes |
| 8 | Output shape | 6 | yes |
| 9 | Scope flags | 3 | medium |
| 10 | Morning agent | 3 | medium (skip if no Slack MCP) |
| 11 | Upgrade notice | 2 | yes |
| 12 | Migration & regression | 4 | yes |

**Total: ~67 tests.** A focused first pass through Phases 1–3 + 6 + 7 + 11 (the user-facing critical path) is ~35 tests and catches most regressions.
