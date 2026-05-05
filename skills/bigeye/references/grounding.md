# Doc grounding

The plugin grounds explanations of BigEye monitor types, dimensions, threshold semantics, and coverage concepts in the BigEye docs site. Citation-first.

## URL conventions

Base URL: `settings.docs.base_url` (default `https://docs.bigeye.com`).

| Topic | Path hint |
|---|---|
| Freshness dimension | `/dimensions/freshness` |
| Volume / row-count dimension | `/dimensions/volume` |
| Uniqueness dimension | `/dimensions/uniqueness` |
| Completeness / null dimension | `/dimensions/completeness` |
| Regex / format monitor | `/monitor-types/regex-match` |
| Range monitor | `/monitor-types/value-range` |
| Profile-based monitors | `/monitors/profile-based` |

When the exact path is unknown: WebFetch the base URL, follow the first matching link in nav, fall back to the search page (`/search?q={topic}`).

## Citation format

Always inline. Per render:

```
... explanation ...
Source: {url}
```

For multi-bullet renders, cite per bullet only when bullets reference different docs pages. Otherwise a single trailing `Source: …` line covers the section.

## Failure mode

WebFetch fails (timeout, 4xx, 5xx) → answer best-effort and append:

```
(docs unreachable — no citation)
```

Never block the parent skill.
