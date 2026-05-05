# Skill discovery checklist (manual)

Run at session start by typing each phrase and checking which skill auto-invokes. Phrases marked **must auto-invoke** the listed skill.

| Phrase | Should auto-invoke |
|---|---|
| "let's go through today's issues" | `bigeye-roster` |
| "walk me through open issues" | `bigeye-roster` |
| "improve monitor 4421" | `bigeye-improve` |
| "tighten the threshold on monitor 4421" | `bigeye-improve` |
| "what gaps does table orders have" | `bigeye-coverage` |
| "find missing monitors on orders" | `bigeye-coverage` |
| "add a hint to my profile" | `bigeye-config` |
| "switch profile to staging" | `bigeye-config` |
| "how does freshness work in BigEye" | `bigeye-docs-grounding` (ambient — confirm citation appears) |
| "what's the difference between completeness and uniqueness" | `bigeye-docs-grounding` (ambient — confirm citation appears) |

**Phrases that must NOT auto-invoke** (regression guard):

| Phrase | Should NOT trigger |
|---|---|
| "I want to dashboard the bigeye state" | NOT `bigeye` (legacy dashboard) — should suggest `/bigeye-roster` instead |
| "triage today's issues" | NOT `bigeye-triage` — should auto-invoke `bigeye-roster` instead |
| "rca on issue 1234" | `bigeye-rca` is acceptable but `bigeye-roster` first-suggestion is preferred |

Each phrase is one row to tick/untick during a session.
