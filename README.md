# BigEye Data Observability Plugin

A Claude Code plugin for managing BigEye monitoring at scale. Simplifies triage, root cause analysis, coverage gaps, monitor deployment, and incident management — all through natural language or slash commands.

## Requirements

- Claude Code with plugin support
- BigEye MCP server configured and authenticated
- Slack MCP server (optional, for morning report notifications)

## Installation

Install directly from the project directory:

```bash
claude plugins install /path/to/bigeye-plugin
```

Or add to your Claude Code settings as a local plugin.

## Commands

| Command | Description |
|---------|-------------|
| `/bigeye` | Smart router — describe what you need in natural language |
| `/bigeye-triage` | Prioritized view of active issues |
| `/bigeye-rca [issue#]` | Root cause analysis with lineage tracing |
| `/bigeye-coverage` | Find monitoring gaps across dimensions |
| `/bigeye-deploy [target]` | Deploy monitors with confirmation |
| `/bigeye-incidents [ids/auto]` | Group related issues into incidents |

## Scheduled Agent

Set up the daily morning report:

```bash
/schedule create "0 8 * * *" /bigeye-morning-report
```

This runs triage every morning at 8am, produces a summary, and sends a Slack notification for critical issues.

## Configuration

Edit `skills/bigeye/references/conventions.md` to customize:
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
