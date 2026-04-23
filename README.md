# BigEye Data Observability Plugin

A Claude Code plugin for managing BigEye monitoring at scale. Simplifies triage, root cause analysis, coverage gaps, monitor deployment, and incident management — all through natural language or slash commands.

## Requirements

- Claude Code with plugin support
- **Bigeye CLI 0.7+** installed and authenticated — see [`bigeye-cli-install.md`](bigeye-cli-install.md)
- **Bigeye MCP server** (optional; unlocks RCA lineage, coverage scoring, incident creation, cluster detection, display-name lookup, and tag tracking) — see [`bigeye-mcp-install.md`](bigeye-mcp-install.md)
- Slack MCP server (optional, for morning report notifications)

## How it works

Every BigEye skill uses the CLI as its primary transport. If the MCP server is also configured, advanced features (lineage, clustering, coverage scoring, incidents) become available transparently. If MCP is not configured, skills still run — affected features print a one-line note pointing at `bigeye-mcp-install.md`.

Run `/bigeye-config verify` at any time to see which features are enabled.

## Installation

Add the marketplace, then install the plugin:

```bash
/plugin marketplace add andriikoziichuk/bigeye-plugin
/plugin install bigeye-plugin@andriikoziichuk-bigeye-plugin
```

## Updating

Refresh the marketplace cache, then reinstall to pull the latest version:

```bash
/plugin marketplace update andriikoziichuk-bigeye-plugin
/plugin install bigeye-plugin@andriikoziichuk-bigeye-plugin
```

Your `~/.claude/bigeye-plugin/profiles.json` is preserved across updates — scope profiles do not need to be re-created after upgrading.

## Commands

| Command | Description |
|---------|-------------|
| `/bigeye` | Smart router — describe what you need in natural language |
| `/bigeye-config [init/show/switch/add/edit/delete]` | Manage scope profiles (workspace + table/source/schema/tag filters) |
| `/bigeye-triage` | Prioritized view of active issues (scope-filtered) |
| `/bigeye-rca [issue#]` | Root cause analysis with lineage tracing |
| `/bigeye-coverage` | Find monitoring gaps across dimensions (scope-filtered) |
| `/bigeye-deploy [target]` | Deploy monitors with confirmation |
| `/bigeye-incidents [ids/auto]` | Group related issues into incidents |

## Scheduled Agent

Set up the daily morning report:

```bash
/schedule create "0 8 * * *" /bigeye-morning-report
```

This runs triage every morning at 8am, produces a summary, and sends a Slack notification for critical issues.

## Configuration

**Scope profiles (per-user):** Run `/bigeye-config init` once after installing the plugin. This creates `~/.claude/bigeye-plugin/profiles.json` with your workspace ID and optional filters (data sources, tables, schemas, tags). Every skill applies the active profile automatically; override per-invocation with `--profile <name>`, `--no-scope`, or `--workspace <id>`.

**Shared conventions:** edit `skills/bigeye/references/conventions.md` to customize:
- Slack channel and mention groups
- Severity classification thresholds
- Output formatting preferences
- Default monitor settings

## Skill Chaining

Skills suggest the logical next step:

```
/bigeye-triage → /bigeye-rca 10921 → /bigeye-incidents 10919 10920 10921
/bigeye-coverage → /bigeye-deploy gaps --priority high
```
