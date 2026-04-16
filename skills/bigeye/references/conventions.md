# BigEye Plugin — Shared Conventions

All BigEye skills MUST read and follow these conventions for consistent output.

---

## Status Display Mapping

| API Status | Display |
|------------|---------|
| ISSUE_STATUS_NEW | New |
| ISSUE_STATUS_ACKNOWLEDGED | Ack'd |
| ISSUE_STATUS_CLOSED | Closed |
| ISSUE_STATUS_MONITORING | Monitoring |
| ISSUE_STATUS_MERGED | Merged |

## Severity Classification

Classify every issue into one of three severity levels:

**Critical:**
- Freshness or Volume dimension issues (pipeline is broken)
- Any issue older than 4 hours still in NEW status
- Any issue with 3+ related downstream issues

**Warning:**
- Data quality dimension issues: Validity, Completeness, Uniqueness
- Issues with 1-2 related downstream issues
- Issues in ACKNOWLEDGED status that are older than 24 hours

**Low:**
- Recently opened issues (< 1 hour) with no related issues
- Distribution or Format dimension issues with no downstream impact
- Issues already in MONITORING status

## Output Formatting

### Issue Tables

Always use this column format for issue listings:

```
| # | Issue | Dimension | Column | Since | Related |
|---|-------|-----------|--------|-------|---------|
| 1 | 10921 | Freshness | — | 2h ago | 2 related |
```

- **#**: Sequential row number
- **Issue**: Display name (the number shown in BigEye UI)
- **Dimension**: The data quality dimension (Freshness, Volume, Validity, etc.)
- **Column**: Column name, or "—" for table-level metrics
- **Since**: Human-readable time since issue opened (e.g., "2h ago", "3d ago")
- **Related**: Count of related issues, or "—" if none

### Severity Indicators

Use these prefixes in summary text:
- Critical issues: no emoji, just bold **Critical**
- Warning issues: **Warning**
- Low issues: **Low**

Do NOT use emoji unless the user explicitly requests it.

### Chaining Suggestions

Every skill output MUST end with a "Suggested next" section pointing to the logical next skill:
- Triage → suggest `/bigeye-rca <top-issue>`
- RCA → suggest `/bigeye-incidents` if multiple related issues, or acknowledge
- Coverage → suggest `/bigeye-deploy gaps`
- Deploy → suggest `/bigeye-triage` to verify monitors collecting data
- Incidents → suggest `/bigeye-rca <root-cause>` for deep dive

## MCP Tool Patterns

### Issue Name Resolution

When the user provides an issue number (display name like "10921"):
1. Call `mcp__bigeye__search_issues` with `name_query: "<number>"`
2. Use the `id` field from the result for all subsequent API calls
3. If multiple matches, ask the user to clarify

### Pagination

When calling `list_issues` or other paginated tools:
1. Start with default page_size (20)
2. If `page_cursor` is returned in result, fetch next page
3. Continue until no more pages or `max_issues` reached
4. For triage, default `max_issues: 50` to avoid context overload

### Error Recovery

If an MCP tool call fails:
1. Report the error clearly to the user
2. Suggest the most likely cause (wrong ID, table not found, permissions)
3. Offer to retry with corrected parameters
4. Never silently skip failures

## Slack Notification Templates

### Configuration

Slack settings (edit these values for your team):
- **Channel**: `#data-quality-alerts`
- **Severity threshold**: Only notify on Critical issues
- **Mention group**: `@data-oncall` for Critical issues
- **MCP tool**: Use `mcp__claude_ai_Slack__*` tools (requires authentication)

### Morning Report Template

```
BigEye Morning Report — {date}

{critical_count} critical | {warning_count} warning | {low_count} low

Top issues:
{top_3_issues_one_line_each}

Coverage: {coverage_percent}%
Run /bigeye-triage in Claude Code for details
```

If critical_count > 0, prepend with `@data-oncall` mention.

### Alert Template (for ad-hoc critical alerts)

```
BigEye Alert — {issue_display_name}
{dimension} issue on {table_name}.{column_name}
Since: {time_since}
Related: {related_count} issues
```

## Tag Conventions

- `deployed-by-plugin`: Applied to all monitors created via `/bigeye-deploy`. Used for tracking and auditing plugin-created monitors.
- Before tagging, call `mcp__bigeye__list_tags` with `search: "deployed-by-plugin"` to check if tag exists.
- If not found, create it with `mcp__bigeye__create_tag` with `name: "deployed-by-plugin"`, `color_hex: "#6366F1"`.

## Priority Mapping

| BigEye Priority | Display |
|----------------|---------|
| ISSUE_PRIORITY_LOW | Low |
| ISSUE_PRIORITY_MED | Medium |
| ISSUE_PRIORITY_HIGH | High |

## Closing Labels

When closing issues, use one of:
- `METRIC_RUN_LABEL_TRUE_NEGATIVE`: Real issue, now resolved
- `METRIC_RUN_LABEL_FALSE_POSITIVE`: Not a real issue (noisy monitor)
