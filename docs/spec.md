Requirements: Bigeye DQ Investigator Agent
1. Purpose
An agent that takes a Bigeye data quality issue, automatically investigates it against Snowflake, and produces a decision-ready resolution memo with a ready-to-paste ticket body. Reduces time-to-diagnosis for SOV data quality issues from manual investigation (typically 30–90 min) to a single conversation turn, while keeping a human in the loop for ticket creation and resolution.
2. Scope
In scope (v1)

All Bigeye issue types (freshness, volume, null rate, distribution, schema, custom metrics)
SOV tables only — tables containing Share of Voice data from retail sites (Amazon, Walmart, Target, etc.)
Manual trigger via chat: user pastes a Bigeye issue ID or link
Snowflake diagnostic querying via Snowflake MCP
Markdown resolution memo delivered in chat, including a ticket body block the developer copy-pastes into Jira/Asana
Manual verification steps for the user when retailer-side investigation is needed (e.g., "check Amazon for keyword X in category Y")

Out of scope (v1, deferred to v2)

Auto-trigger from Bigeye webhooks or scheduled polling
Slack channel delivery
Automated ticket creation in Jira/Asana
Live retailer browsing (Claude in Chrome on Amazon/Walmart)
Non-SOV tables
Resolution actions (running fixes, reverting data, etc.) — agent diagnoses only, never modifies data

3. Functional requirements
3.1 Input

FR-1.1 Accept a Bigeye issue ID, issue display name (e.g., "I-1234"), or full Bigeye issue URL pasted in chat.
FR-1.2 If input is ambiguous (multiple matches), present options and ask the user to pick.
FR-1.3 Reject inputs that resolve to non-SOV tables with a clear message naming the matched table, so the user knows why it was rejected.

3.2 Context gathering (Bigeye)

FR-2.1 Fetch full issue details: metric, threshold, current value, severity, opened-at, status, priority.
FR-2.2 Fetch metric history and the recent window of values around the breach.
FR-2.3 Fetch table profile: row count, column stats, recent profile runs.
FR-2.4 Fetch upstream lineage and any open issues on upstream nodes.
FR-2.5 Fetch related issues on the same table within the last 30 days.
FR-2.6 Identify the SOV-specific attributes of the table: which retailer, which category/keyword dimensions, what time grain.

3.3 Investigation (Snowflake)

FR-3.1 Select a diagnostic playbook based on issue type (one per type: freshness, volume, null, distribution, schema, custom).
FR-3.2 Generate and execute Snowflake SQL queries following the playbook. Queries must be read-only (SELECT only; reject any INSERT/UPDATE/DELETE/MERGE/CREATE/DROP/ALTER/TRUNCATE).
FR-3.3 Branch query selection based on prior result. Examples: if volume drop and partition-level query shows one retailer missing → drill into that retailer's load history. If null spike confined to one column → check upstream source for that field.
FR-3.4 Cap investigation at a configurable budget (default: 10 queries per investigation) and surface a warning if the cap is reached without confident diagnosis.
FR-3.5 Persist every executed query and its result in the investigation trace.
FR-3.6 Detect when the issue likely requires retailer-side verification (e.g., legitimate-looking SOV drop with no upstream data anomaly) and switch to producing manual verification steps instead of more queries.

3.4 SOV domain knowledge

FR-4.1 Maintain a knowledge file listing known SOV failure patterns per retailer, ranked by frequency (e.g., "Amazon category restructure", "Walmart PDP layout change", "scraper rate-limit", "competitor entry", "seasonality").
FR-4.2 When the investigation matches a known pattern, the resolution memo names the pattern and links to the playbook entry.
FR-4.3 The knowledge file is editable by the team without code changes (markdown, loaded by the skill at runtime).

3.5 Output

FR-5.1 Produce a structured markdown memo with these sections:

Summary — one-sentence root cause statement + confidence (high/medium/low).
Issue context — table, retailer, metric, breach details.
Investigation trace — each query, what it tested, result summary, what it ruled in or out.
Root cause — the explanation, with evidence references.
Suggested next steps — for the human, including any manual retailer verification steps when relevant.
Ticket body — a copy-pasteable block with title, description, severity, suggested assignee/team, and a labeled section for SQL evidence.


FR-5.2 If confidence is low or the investigation budget was exhausted, the memo says so explicitly and lists what remains untested.
FR-5.3 Ticket body must be plain markdown the developer can drop into Jira or Asana without reformatting.
FR-5.4 If a ticket template for the matched issue type exists in the team's template library, use it; otherwise generate a freeform memo with all the same fields.

4. Non-functional requirements

NFR-1 Read-only against Snowflake. Hard rule, enforced by query validation before execution.
NFR-2 Investigation completes within ~3 minutes wall-clock for typical issues; longer is acceptable but the agent streams progress so the user sees what's happening.
NFR-3 Every query and every Bigeye API call is logged in the trace so a human can reproduce the investigation.
NFR-4 Agent never claims certainty it doesn't have — confidence ratings are required on every root cause statement.
NFR-5 Skill description triggers reliably on phrasings like "investigate Bigeye issue X", "diagnose I-1234", "what's wrong with table Y", and on a pasted Bigeye URL alone.
NFR-6 Domain knowledge and playbooks live in editable markdown files; adding a new retailer or a new failure pattern does not require code changes.

5. Integrations
SystemUseMethodBigeyeIssue context, lineage, profiles, related issuesBigeye MCP server (already connected)SnowflakeDiagnostic query executionSnowflake MCP server (already connected)SOV knowledge baseFailure patterns per retailerMarkdown file in the skillTicket templatesPer-issue-type templatesMarkdown files in the skill
6. Out-of-scope guardrails
The agent must refuse and explain when asked to:

Run write queries against Snowflake
Modify Bigeye issues (close, reassign, comment) — read-only in v1
Create tickets directly in Jira/Asana
Investigate non-SOV tables
Bypass the query budget or read-only restriction

7. Success criteria

SC-1 On a labeled set of 20 historical SOV issues, the agent's root cause matches the team's recorded resolution on ≥70% with high or medium confidence.
SC-2 Median end-to-end time from issue-ID-pasted to memo-delivered ≤ 3 minutes.
SC-3 Ticket bodies require no structural editing before the developer pastes them — only content tweaks.
SC-4 Zero write operations against Snowflake across all runs in the eval period.

8. Open questions for next pass
These don't block requirements but will shape the spec:

Which Snowflake user/role does the agent connect as? Needs read on SOV schemas, no write anywhere. Likely a dedicated service role.
Where do playbooks and SOV knowledge live — inside the skill repo, or in a Notion/Drive doc the skill fetches? Repo is simpler; Drive lets non-engineers edit.
Confidence calibration — how does the agent decide high vs medium vs low? Need a rubric (e.g., "high = single hypothesis fits all evidence, no contradicting signals").
Investigation budget — 10 queries the right ceiling? Should it differ by issue type?
Multi-issue mode — if the user pastes 3 issue IDs, does the agent investigate each separately or look for a common root cause? v1 default: separate, with a note if they look related.