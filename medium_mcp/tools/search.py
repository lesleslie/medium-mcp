from __future__ import annotations

from medium_mcp.cache.store import MediumCache
from medium_mcp.clients.medium2 import Medium2Client
from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient
from medium_mcp.models.dto import (
    SearchArticlesPage,
    SearchPublicationsPage,
    SearchUsersPage,
)


async def search_articles(
    *,
    settings: MediumSettings,
    dhara: DharaClient,
    cache: MediumCache,
    client: Medium2Client,
    query: str,
    cursor: str | None = None,
) -> SearchArticlesPage:
    params = {"query": query, "cursor": cursor}
    raw = await cache.get_or_compute(
        "search_articles",
        params,
        lambda: client.request("search_articles", params, tool_name="search_articles"),
    )
    return SearchArticlesPage.model_validate(raw)


async def search_users(
    *,
    settings: MediumSettings,
    dhara: DharaClient,
    cache: MediumCache,
    client: Medium2Client,
    query: str,
    cursor: str | None = None,
) -> SearchUsersPage:
    params = {"query": query, "cursor": cursor}
    raw = await cache.get_or_compute(
        "search_users",
        params,
        lambda: client.request("search_users", params, tool_name="search_users"),
    )
    return SearchUsersPage.model_validate(raw)


async def search_publications(
    *,
    settings: MediumSettings,
    dhara: DharaClient,
    cache: MediumCache,
    client: Medium2Client,
    query: str,
    cursor: str | None = None,
) -> SearchPublicationsPage:
    params = {"query": query, "cursor": cursor}
    raw = await cache.get_or_compute(
        "search_publications",
        params,
        lambda: client.request("search_publications", params, tool_name="search_publications"),
    )
    return SearchPublicationsPage.model_validate(raw)
