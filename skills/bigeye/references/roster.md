# Roster — facts, recommendation, action handlers

## Fact gathering (per issue)

For each issue, gather up to `roster.max_facts_per_issue` (default 6) facts:

| Fact | Source | Cost |
|---|---|---|
| `current_metric` | `mcp__bigeye__get_issue` | 1 call |
| `metric_trend` (last N runs, default 30 days) | `mcp__bigeye__list_table_metrics` filtered to monitor | 1 call |
| `recurrence_count` (last 90d for same monitor) | `mcp__bigeye__search_issues(monitor_id=…)` | 1 call |
| `matching_hints` | local `profiles[active].custom_hints` filtered by scope+target | 0 calls |
| `profile_drift` | `mcp__bigeye__get_table_profile` delta vs prior snapshot | 1 call (cache 24h per table) |

Skip any fact whose source returns an MCP error; mark with `(unavailable)` in the rendered fact list. Do not hard-fail the loop.

## Recommendation derivation

Given the gathered facts, choose ONE primary recommendation. Tiebreak in this order:

**Precedence:** evaluate the rows below top-to-bottom; the first matching row wins. The investigate/ticket routing rules come BEFORE the numbered tiebreak list (`1.` close-on-recovery, etc.) because diagnosable issues should be investigated before being tiebroken into a close/skip action.

| Condition | Recommendation |
|---|---|
| Issue type ∈ {freshness, volume, null, distribution, schema, custom} AND age < 24h AND no prior `bigeye-investigate` action on this issue | `v` (investigate — diagnose with Snowflake-backed pack) |
| Same type, prior `bigeye-investigate` exists with confidence ∈ {high, medium} | `t` (ticket — already diagnosed) |

1. **`close — metric recovered`** if `current_metric` is back under threshold AND stable for ≥2 consecutive runs in `metric_trend`.
2. **`close — within user noise floor`** if any `matching_hints` is `noise_threshold` AND the issue's current delta % ≤ `delta_pct_max`.
3. **`improve`** if `recurrence_count >= 5` AND deltas have a small consistent magnitude (`|delta| < 10%` across the trend).
4. **`ticket`** if `profile_drift` is detected (column null-rate shift > 5pp, or row-count shift > 25%).
5. **`investigate`** otherwise — describes the facts, recommends manual review.

## Render template

```
[Issue #{id} — {table}.{column} {dimension}, severity {sev}]
Facts:
  • {fact 1}
  • {fact 2}
  ...
Recommendation: {one sentence}
                {one-line "why" referencing the rule above}
                Source: {doc URL — see grounding.md}
Action? [i]mprove  [v]investigate  [c]lose  [f]laky-note  [t]icket  [h]int  [s]kip
```

Each line under `Facts:` is one short clause. No nested bullets. Cap each fact at 80 columns.

The `Source:` line is filled by delegating to `bigeye-docs-grounding` with the issue's dimension as the topic. Do not fabricate URLs locally.

## Action handlers

| Key | Handler |
|---|---|
| `c` | Ask for one-line reason. Call `mcp__bigeye__update_issue(issue_id, status=CLOSED, reason=<user>)`. Append `{issue_id, action:"close", reason, ts}` to `state.json`. |
| `f` | Ask for one-line note. Call `mcp__bigeye__update_issue(issue_id, status=ACKNOWLEDGED, note=<user prefixed with "[flaky] ">)`. Append `{action:"flaky"}` to `state.json`. |
| `t` | Render markdown ticket via the existing `bigeye-ticket` skill (via Skill tool, passing `<issue_id>`). Print result to terminal. Append `{action:"ticket"}` to `state.json`. Continue. |
| `i` | Print: `Run /bigeye-improve <monitor_id> to deep-analyze this monitor.` Append `{action:"improve_suggested"}`. Continue. |
| `v` | See `[v]` handler block below. |
| `h` | Trigger `/bigeye-config hints add` flow (Skill tool) with scope/target pre-filled to this issue's monitor or table. After save, re-evaluate facts for the current issue and re-render. Treat re-rendered prompt as a fresh action choice. |
| `s` | Append `{action:"skip"}`. Continue to next issue. |

### `[v]` — investigate

1. Resolve the pack: call `PackLoader.resolve_pack_for_tags(issue.tags)`. If the resolved pack is `_default`, set `using_default = true`.
2. Read `profiles.json[active].snow.profile`. If unset, print:
   ```
   Error: No Snowflake profile configured for /bigeye-investigate.
   Fix:   /bigeye-config snow set <profile>
   Why:   roster's [v] action handler requires a snow profile.
   ```
   Treat as `[s]kip`.
3. Confirm:
   ```
   Investigate I-{id}? snow=<profile>, pack=<resolved>, budget=10. (y/n)
   ```
   If `using_default`, prepend:
   ```
   No domain pack matched tags <list>. Using _default.
   ```
4. On `y`: invoke `/bigeye-investigate <id>` as a sub-skill. Roster loop pauses until it returns. On return:
   - Append `{ skill: "bigeye-roster", action: "investigate", at: <iso8601>, confidence: <high|medium|low> }` to `state.json.issues[<id>].actions`.
   - Print `Continuing roster from I-<next_id>.`
   - Continue to next issue.
5. On `n`: same behavior as `[s]kip`.

If MCP write fails for `c` or `f`: print the error block (Error/Fix/Why), keep issue open, ask `Try again, skip, or stop? (r/s/x)`.

## Pacing

Process in batches of `roster.batch_size`. After each batch:

```
Batch {N} complete. {x} closed, {y} flaky-noted, {z} tickets, {q} improvements suggested, {s} skipped.
Continue? (y/n)
```

`n` → end-of-pass summary:

```
Roster complete — N issues reviewed.
  close: x    flaky-note: y    ticket: z
  improve suggested: q    investigate: v    hint added: h    skip: s
```

## Resumability

Each action appended to `state.json` under `state.issues[<id>].actions`. On the next `/bigeye-roster` invocation, skip any issue whose newest `action` is in `{close, flaky, skip}` and whose timestamp is within the last 24 hours. Override with `--include-actioned`.
