# BigEye Data Observability Plugin

A Claude Code plugin for managing BigEye monitoring at scale — built around two workflows (reactive triage and proactive table audits), backed by a persistent dashboard, and chained through atomic skills with consistent output and a local activity log.

## What's new in 0.4.0

- **Two workflow commands** — `/bigeye-today` (reactive: triage → act → loop) and `/bigeye-table <name>` (proactive: audit a table → act → loop). These compose the existing atomic skills; you don't have to remember which command to chain next.
- **`/bigeye` is now a dashboard.** One-pass snapshot of your scope: open issues, recent activity, per-table coverage, last actions. Non-interactive.
- **Settings file.** User-editable values (Slack channel, severity thresholds, deploy defaults, default view) moved out of plugin files into `~/.claude/bigeye-plugin/settings.json`. Manage via `/bigeye-config settings show` / `settings edit <key> <value>`.
- **Activity log.** A new `~/.claude/bigeye-plugin/state.json` records every skill action per issue and per table. No-arg forms (`/bigeye-rca`, `/bigeye-coverage`, `/bigeye-improve`, `/bigeye-table`) resume from where you left off.
- **Standardized output.** Scope pill, Brief/Full sizing, `Next:`/`More:` footer, `Error / Fix / Why` blocks across every skill.
- **Backwards-compatible on disk.** No command renames or removals. `profiles.json` and ticket templates are preserved on upgrade.

If you customized the old `conventions.md` reference (Slack channel or severity thresholds) in a previous version, those edits are not migrated automatically — re-apply them via `/bigeye-config settings edit slack.channel '#your-channel'`, etc.

## Requirements

- Claude Code with plugin support
- **Bigeye CLI 0.7+** installed and authenticated — see [`bigeye-cli-install.md`](bigeye-cli-install.md)
- **Bigeye MCP server** (optional; unlocks RCA lineage, coverage scoring, incident creation, cluster detection, display-name lookup, and tag tracking) — see [`bigeye-mcp-install.md`](bigeye-mcp-install.md)
- Slack MCP server (optional, for morning report notifications)

## Installation

```bash
/plugin marketplace add andriikoziichuk/bigeye-plugin
/plugin install bigeye-plugin@andriikoziichuk-bigeye-plugin
```

After install: `/bigeye-config init` once to bind your workspace and scope filters.

## Workflows (start here)

| Command | When to use |
|---|---|
| `/bigeye` | Quick snapshot — what's the state of my scope right now? |
| `/bigeye-today` | Something's broken — show me open issues, let me act. |
| `/bigeye-table <name>` | Audit a table — coverage, weak monitors, gaps, table-scoped issues. |

## Atomic skills (called by workflows; usable directly too)

| Command | Description |
|---|---|
| `/bigeye-config [init/show/switch/add/edit/delete/verify/settings show/settings edit]` | Manage scope profiles (`profiles.json`) and user settings (`settings.json`). |
| `/bigeye-triage [new/24h/<N>]` | Prioritized active issues, scope-filtered. |
| `/bigeye-rca [issue]` | Root-cause analysis with lineage tracing. No-arg → resumes `last_issue`. |
| `/bigeye-coverage [table]` | Dimension/column gaps + cheap weak-monitor scan. No-arg → resumes `last_table`. |
| `/bigeye-improve [table]` | Deep monitor recommendations + heavy-mode SQL refinement loop. No-arg → resumes `last_table`. |
| `/bigeye-deploy [target]` | Create monitors with confirmation gate. |
| `/bigeye-incidents [ids/auto/add/close]` | Group related issues into incidents. |
| `/bigeye-ticket [issue]` | Render a markdown vendor ticket from a user-authored template. |

## Scheduled agent

Set up the daily morning report:
```bash
/schedule create "0 8 * * *" /bigeye-morning-report
```
The agent calls `/bigeye-today --report-only` under the hood and posts to Slack (`settings.json.slack.channel`).

## Configuration

**Scope profiles** (`~/.claude/bigeye-plugin/profiles.json`) — owned by `/bigeye-config`. Workspace + filter sets (data sources, tables, schemas). Per-invocation overrides: `--profile <name>`, `--no-scope`, `--workspace <id>`.

**Settings** (`~/.claude/bigeye-plugin/settings.json`) — Slack channel, severity thresholds, deploy defaults, default view. Seeded on first run. Edit via `/bigeye-config settings show` / `settings edit <key> <value>`.

**Activity log** (`~/.claude/bigeye-plugin/state.json`) — append-only, LRU-pruned (last 500 issues, last 100 tables). Backs no-arg fallbacks and the dashboard's "History" / "Recently closed" sections.

**Ticket templates** (`~/.claude/bigeye-plugin/ticket-templates/`) — managed via `/bigeye-ticket templates add/edit/delete/list`. Seeded with a `default.md` on first run.

## How features degrade without MCP

The Bigeye CLI is the primary transport. MCP unlocks lineage, clustering, coverage scoring, incidents, display-name lookup, profile data, and tag tracking. When MCP is unavailable, every skill prints a one-line note and continues with whatever the CLI alone can show. Some operations hard-fail (coverage scoring, incident creation, display-name lookup) — those skills print a clear pointer to `bigeye-mcp-install.md`.

Run `/bigeye-config verify` to see exactly what's enabled.
