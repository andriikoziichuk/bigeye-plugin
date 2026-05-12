# BigEye Data Observability Plugin

A Claude Code plugin focused on three workflows: a daily roster routine over open BigEye issues, single-monitor improve, and an interactive batch coverage proposal. Plus an ambient docs-grounding layer — every monitor / dimension / threshold explanation is cited back to the BigEye docs site.

## What's new in 0.6.0

- **`/bigeye-investigate <issue>` (new).** Read-only Snowflake investigation, pack-driven, confidence-rated memo + paste-ready ticket body. Dispatches the `bigeye-investigator` subagent.
- **Pack format + `/bigeye-pack new <name>`.** Domain knowledge (hypotheses, playbooks, manual verification) lives in `~/.claude/bigeye-plugin/packs/<name>/`, loaded by BigEye tag.
- **`/bigeye-config snow set/show/unset/verify`.** Bind a Snowflake `snow` CLI connection to each BigEye profile. `verify` warns if the role has write grants.
- **Roster `[v]` investigate action.** Recommended on diagnosable-shape issues.

## What's new in 0.5.0

- **Three pillars only on the user surface.** `/bigeye-roster`, `/bigeye-improve <monitor_id>`, `/bigeye-coverage <table>`.
- **`/bigeye-roster` (new).** Daily routine: walk open issues, see facts + recommendation per issue, pick close / flaky-note / ticket / improve / hint / skip. Advisory only — never auto-closes.
- **Custom hints.** Author per-table or per-monitor advisory rules in plain text via `/bigeye-config hints add`. Plugin compiles to a structured predicate before saving.
- **Interactive coverage.** `/bigeye-coverage <table>` walks columns one at a time, shows the auto-detected profile, asks what the column actually holds, and proposes monitors that fit.
- **MCP-only.** The BigEye CLI is no longer required for the user-facing pillars. CLI-based hidden skills remain on disk and callable.
- **Doc grounding.** Every monitor / dimension explanation cites the matching BigEye docs URL.

## Requirements

- Claude Code with plugin support
- **BigEye MCP server** authenticated against your workspace — see [`bigeye-mcp-install.md`](bigeye-mcp-install.md)

(Slack MCP optional, only used by the legacy morning-report agent.)

## Installation

```bash
/plugin marketplace add andriikoziichuk/bigeye-plugin
/plugin install bigeye-plugin@andriikoziichuk-bigeye-plugin
```

After install: `/bigeye-config init` to bind your workspace and scope.

## Commands

| Command | Description |
|---|---|
| `/bigeye-roster` | Daily routine — walk open issues, act on each |
| `/bigeye-improve <monitor_id>` | Single-monitor improve — read-only proposal grounded in profile data and validated with SQL |
| `/bigeye-coverage <table>` | Interactive batch proposal — per-column conversation, fitted monitors |
| `/bigeye-config [subcmd]` | Profiles + custom hints + virtual tables + settings |
| `/bigeye-investigate <issue>` | Read-only Snowflake-backed root-cause investigation. Returns memo + paste-ready ticket body |
| `/bigeye-pack new <name>` | Scaffold a new domain pack interactively. Includes `lint`, `list` |

## Daily flow

```
/bigeye-roster                      # walk issues, advisory recs per issue
   ↓
[i]mprove on a flagged issue        # → /bigeye-improve <monitor_id>
[c]lose / [f]laky-note / [v]nvestigate inline  # MCP write per action
[h]int adds advisory rule to profile
   ↓
/bigeye-coverage <table>            # find gaps, propose monitors
   ↓
/bigeye-deploy …                    # apply (callable, hidden surface)
```

## Configuration

**Profiles** (`~/.claude/bigeye-plugin/profiles.json`) — workspace + scope (data sources / schemas / tables / virtual tables) + monitored rules + custom hints. Owned by `/bigeye-config`. Per-invocation overrides: `--profile <name>`, `--no-scope`, `--workspace <id>`.

**Settings** (`~/.claude/bigeye-plugin/settings.json`) — Slack channel (legacy), severity thresholds (legacy), `docs.base_url`, `roster.batch_size`, `roster.max_facts_per_issue`. Edit via `/bigeye-config settings show` / `settings edit <key> <value>`.

**Activity log** (`~/.claude/bigeye-plugin/state.json`) — append-only, LRU-pruned. Powers roster resumability and the `(no-arg)` resume on coverage / improve.

## Without MCP

The user-facing pillars hard-fail with:

```
MCP unreachable. Try:
  1. /mcp reconnect bigeye
  2. Retry the command
If still failing: see bigeye-mcp-install.md
```

Run `/bigeye-config verify` to see exactly what's reachable.
