from __future__ import annotations

from typing import Literal

from medium_mcp.cache.store import MediumCache
from medium_mcp.clients.medium2 import Medium2Client
from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient
from medium_mcp.dhara.keys import content_key
from medium_mcp.models.dto import (
    ArticleContent,
    ArticleMetadata,
    ArticleResponsesPage,
)


async def article_metadata(
    *,
    settings: MediumSettings,
    dhara: DharaClient,
    cache: MediumCache,
    client: Medium2Client,
    article_id: str,
) -> ArticleMetadata:
    params = {"article_id": article_id}
    raw = await cache.get_or_compute(
        "article_metadata",
        params,
        lambda: client.request("article_metadata", params, tool_name="article_metadata"),
    )
    return ArticleMetadata.model_validate(raw)


async def article_content(
    *,
    settings: MediumSettings,
    dhara: DharaClient,
    cache: MediumCache,
    client: Medium2Client,
    article_id: str,
    include_full_text: bool = False,
    format: Literal["markdown", "html", "text"] = "markdown",
) -> ArticleContent:
    """Spec §6.2 content policy:
    1. ``include_full_text`` defaults to False.
    2. Full text cached under a separate ``content_key`` prefix.
    3. Return is gated independently of cache state.
    """
    # Always fetch metadata for the excerpt + canonical fields.
    metadata = await article_metadata(
        settings=settings,
        dhara=dhara,
        cache=cache,
        client=client,
        article_id=article_id,
    )

    full_text: str | None = None
    truncated = False
    if include_full_text:
        # Reach the upstream only on opt-in. Cached under content prefix.
        cached = await dhara.get(content_key(article_id))
        if cached is None:
            up = await client.request(
                "article_content",
                {"article_id": article_id},
                tool_name="article_content",
            )
            full_text = up.get("content", {}).get("body", "") or ""
            await dhara.put(
                content_key(article_id),
                full_text.encode(),
                ttl=settings.cache_ttl_article_content,
            )
        else:
            full_text = cached.decode()

    excerpt = metadata.excerpt or ""
    if len(excerpt) > settings.excerpt_max_chars:
        excerpt = excerpt[: settings.excerpt_max_chars]
        truncated = True

    return ArticleContent(
        article_id=article_id,
        excerpt=excerpt,
        full_text=full_text if include_full_text else None,
        format=format,
        truncated=truncated,
        include_full_text=include_full_text,
    )


async def article_responses(
    *,
    settings: MediumSettings,
    dhara: DharaClient,
    cache: MediumCache,
    client: Medium2Client,
    article_id: str,
    cursor: str | None = None,
) -> ArticleResponsesPage:
    params = {"article_id": article_id, "cursor": cursor}
    raw = await cache.get_or_compute(
        "article_responses",
        params,
        lambda: client.request("article_responses", params, tool_name="article_responses"),
    )
    return ArticleResponsesPage.model_validate(raw)
