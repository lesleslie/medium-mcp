# medium-mcp content policy

## Context

Spec §6.2 lays out five rules governing the `article_content` tool. They are
load-bearing because the upstream (medium2 on RapidAPI) is a paid metered API
and the body of any article is the most expensive piece of data the tool can
return. Default-deny is the only posture that keeps the budget guard honest.

## Decision rules

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

## Status

Implemented by Task 9 (`medium_mcp/tools/articles.py`). Pinned by
`tests/unit/test_tools.py::test_article_content_returns_none_when_flag_false`
and the integration counterpart. Enforced at the tool layer (cache may
hold full text; the gate is at return time).
