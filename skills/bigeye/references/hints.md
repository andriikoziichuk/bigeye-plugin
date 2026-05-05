# Custom Hints — compile + storage spec

Custom hints are advisory inputs the roster analyzer surfaces as facts when an open issue matches their `scope` and `target_id`. They never auto-close anything.

## Storage shape

```json
{
  "scope": "table" | "monitor",
  "target_id": <int>,
  "target_name": "<string>",
  "raw": "<verbatim user NL>",
  "compiled": <one of the three shapes below>,
  "created_at": "<iso8601>"
}
```

## Three compiled shapes (the only ones allowed)

### `noise_threshold`

```json
{ "type": "noise_threshold", "metric": "<row_count|null_pct|freshness_seconds|...>", "delta_pct_max": <float> }
```

Use when the user expresses "ignore deltas under X%" or "noise floor of Y%". Roster surfaces a fact: `User noise floor for {metric}: {delta_pct_max}%`. Roster compares the issue's current delta against `delta_pct_max`; if smaller, recommendation reads "within user noise floor — close suggested".

### `expected_pattern`

```json
{ "type": "expected_pattern", "when": "weekend|weekday|hour_<H>|day_<DOW>", "metric": "<metric>" }
```

Use when the user says "weekend spikes are expected for X" or "every Sunday batch lag". Roster matches issue `opened_at` against `when` and surfaces `Matches expected pattern: {when}` if applicable.

### `context`

```json
{ "type": "context", "text": "<user's verbatim text>" }
```

Use when the NL doesn't clearly map to threshold or schedule. Roster surfaces the text verbatim under `Custom hint:`. No pattern matching.

## Compile prompt (used by `/bigeye-config hints add`)

Given user NL, scope (`table` or `monitor`), and the resolved `target_name`:

1. Try to detect a `noise_threshold` shape. Trigger words: `ignore`, `noise`, `under`, `below`, `<`, percentage references combined with a metric name.
2. Else try `expected_pattern`. Trigger words: `weekend`, `weekday`, `Sunday`, `every Monday`, `hour`, `morning`, `nightly batch`.
3. Else fall back to `context` with the verbatim text.
4. If multiple shapes match, ask the user to disambiguate. Do not silently pick.
5. If the metric name in a `noise_threshold` is ambiguous (e.g. user said "delta" without specifying), ask. Do not guess.

Always show the compiled JSON to the user and ask `Save this hint? (y/n)` before writing. Refuse to save if user replies anything other than `y`/`yes`.
