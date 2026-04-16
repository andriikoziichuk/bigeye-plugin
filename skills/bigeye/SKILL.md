---
name: bigeye
description: Use when the user mentions BigEye, data quality issues, monitoring gaps, data freshness, monitor coverage, issue triage, root cause analysis, or when BigEye MCP tools are being used in conversation. Routes to the appropriate BigEye sub-skill.
user-invocable: true
---

# BigEye Data Observability Hub

Central entry point for all BigEye monitoring workflows. Routes to the right sub-skill based on user intent.

**Before doing anything else**, read `skills/bigeye/references/conventions.md` for shared formatting and severity rules.

## Available Skills

| Skill | Command | Purpose |
|-------|---------|---------|
| Triage | `/bigeye-triage` | What's on fire? Prioritized active issues |
| Root Cause Analysis | `/bigeye-rca` | Why is this broken? Lineage-traced diagnosis |
| Coverage | `/bigeye-coverage` | What's not monitored? Dimension/column gaps |
| Deploy | `/bigeye-deploy` | Set up monitors with sensible defaults |
| Incidents | `/bigeye-incidents` | Group related issues into incidents |

## Routing

Parse the user's input and invoke the matching sub-skill using the Skill tool:

| User intent | Invoke |
|-------------|--------|
| "what's broken?", "show active issues", "what's on fire", "triage", "status" | Skill: `bigeye-triage` |
| "why is issue X failing?", "what caused this?", "root cause", "trace", "debug" | Skill: `bigeye-rca` with issue reference as args |
| "what's not monitored?", "find gaps", "coverage", "missing monitors" | Skill: `bigeye-coverage` |
| "add monitors", "deploy", "set up monitoring", "create metric" | Skill: `bigeye-deploy` |
| "group issues", "create incident", "merge issues", "incident" | Skill: `bigeye-incidents` |

## Ambiguous Intent

If the user's intent doesn't clearly match one skill, present this menu:

```
What would you like to do?

1. **Triage** — See active issues prioritized by severity (`/bigeye-triage`)
2. **Root Cause Analysis** — Trace why an issue is happening (`/bigeye-rca`)
3. **Coverage** — Find monitoring gaps (`/bigeye-coverage`)
4. **Deploy Monitors** — Set up new monitors (`/bigeye-deploy`)
5. **Incidents** — Group related issues (`/bigeye-incidents`)
```

## With Arguments

If invoked as `/bigeye <text>`, pass `<text>` through the routing logic above. Examples:
- `/bigeye what's broken` → invoke `bigeye-triage`
- `/bigeye rca 10921` → invoke `bigeye-rca` with args `10921`
- `/bigeye coverage columns email` → invoke `bigeye-coverage` with args `columns email`
