---
name: bigeye-docs-grounding
description: Use whenever you are about to explain a BigEye monitor type, dimension, threshold semantic, coverage concept, or any BigEye behavior to the user. Fetches the relevant page from the BigEye docs site and cites the URL inline. Auto-invoked by other BigEye skills (roster / improve / coverage / config) when their renders explain a concept.
user-invocable: false
---

# BigEye Docs Grounding (ambient)

Not a slash command. Invoked transparently when another BigEye skill (or a free-form user question) is about to explain a BigEye concept.

Follow `skills/bigeye/references/grounding.md` for URL conventions and citation format.

## Procedure

1. Read `settings.docs.base_url` (default `https://docs.bigeye.com`). If `settings.json` is missing, fall back to the default without writing.
2. Build a candidate URL from the topic using the path hints in `references/grounding.md`. Always fall back to a single search-page URL if the topic isn't in the table.
3. WebFetch the candidate URL.
4. Extract the heading + first useful paragraph relevant to the topic. Trim to ≤ 250 words.
5. Return the answer in the parent's voice (never insert "I fetched docs" framing) — caller renders. Always end with:
   ```
   Source: {url}
   ```
6. WebFetch failure → return best-effort knowledge and append:
   ```
   (docs unreachable — no citation)
   ```

## Caching

No local cache. WebFetch's per-request cache is sufficient. If the same topic is grounded multiple times in one session, allow re-fetch.

## Errors

Never raises. Failures degrade to "(docs unreachable — no citation)".
