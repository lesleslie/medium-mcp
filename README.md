# medium-mcp

MCP server for Medium content via the unofficial **medium2** RapidAPI.

## Capabilities

13 tools + the free budget readout:

- `user_info` (one-of `user_id` / `username`)
- `user_articles`
- `article_metadata`
- `article_content` (full text opt-in, see Content policy below)
- `article_responses`
- `publication_info` (one-of `publication_id` / `slug`)
- `publication_articles`
- `tag_info`
- `tag_latest`
- `search_articles`
- `search_users`
- `search_publications`
- `budget_remaining` — local read, never hits RapidAPI

## Source

Data comes from the unofficial **medium2** API on RapidAPI. The official Medium
API was archived March 2023 and does not accept new integrations; medium-mcp is
the project that documents what shape the unofficial API returns and how the
budget guard turns it into a metered-but-capped service.

## Setup

1. Sign up at https://rapidapi.com and subscribe to medium2 (free tier: 150
   calls / month).

1. Export the key:

   ```bash
   export MEDIUM_MCP_RAPIDAPI_KEY=<your-key>
   ```

1. Install + run:

   ```bash
   uv pip install -e ".[dev]"
   medium-mcp
   ```

## Health

Two routes, answering different questions:

- **`/health`** — always HTTP 200. Reports per-feed detail in `components`.
  For orchestrators and `curl` smoke probes.
- **`/readyz`** — HTTP 503 when a required feed has not yet returned data,
  200 otherwise. For readiness probes.

`dhara` is a required feed (the budget counter rides on it), so a freshly
started server returns 503 on `/readyz` until a tool call succeeds. That is
intentional: a server whose counter has never been touched cannot guarantee
its budget, and lies would defeat the only guard we have.

## Budget

The server enforces a strict monthly budget (`medium_mcp.budget.monthly_budget`,
default **150 metered calls / period**) under a Dhara-backed advisory lock.
Once exhausted, metered calls are refused with this payload:

```json
{
  "error": "budget_exhausted",
  "remaining_calls": 0,
  "requested_calls": 1,
  "period": "2026-09",
  "resets_at": "2026-10-01T00:00:00Z",
  "retryable": false,
  "cached_alternatives": ["user_info", "article_metadata", "tag_info"]
}
```

`budget_remaining` is always free; it reads the counter locally and reports
`calls_used`, `remaining_calls`, `monthly_budget`, `period`, `resets_at` so
the caller can decide whether to make the call themselves.

## Content policy

`article_content` returns the full body only when the caller passes
`include_full_text=True`. Five rules govern what the tool does and does not
return, in order:

1. **Default-deny.** `article_content` returns `excerpt` only when
   `include_full_text=False`, regardless of cache state. The cache may hold
   `full_text` under the `content_key` prefix; the gate is at the return
   point, not the cache key.
1. **Opt-in body.** Set `include_full_text=True` to receive `full_text`
   alongside the excerpt. The cache hit path also honors the flag — a cached
   body is *only* returned when the flag was set.
1. **Truncation.** `excerpt` is capped at `excerpt_max_chars` (default 500,
   max 2000) so a caller never receives an unbounded body. The
   `truncated: bool` field tells the caller whether the cap fired.
1. **Format.** `format` is one of `"markdown"`, `"html"`, or `"text"`. The
   tool does not transcode between formats; what the upstream returned is
   what the tool returns, gated only by the include flag.
1. **No export.** `allow_content_export: bool` (default `false`) is a
   hard-stop on writing full text to disk or to a downstream store. Treat
   the body as in-memory-only; do not persist it.

The settings section (`MEDIUM_MCP_*` env vars, prefix-defined) carries
`excerpt_max_chars`, `allow_content_export`, `monthly_budget`, and the
rest. See `settings/medium-mcp.yaml` for the full list.

## License

BSD-3-Clause.
