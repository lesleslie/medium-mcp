from __future__ import annotations

from medium_mcp.cache.store import MediumCache
from medium_mcp.clients.medium2 import Medium2Client
from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient
from medium_mcp.models.dto import PublicationArticlesPage, PublicationInfo
from medium_mcp.utils.exceptions import ConfigurationError


async def publication_info(
    *,
    settings: MediumSettings,
    dhara: DharaClient,
    cache: MediumCache,
    client: Medium2Client,
    publication_id: str | None = None,
    slug: str | None = None,
) -> PublicationInfo:
    provided = [p for p in (publication_id, slug) if p is not None]
    if len(provided) != 1:
        raise ConfigurationError(
            "exactly one of publication_id or slug required",
            context={"provided": provided},
        )
    field = "publication_id" if publication_id is not None else "slug"
    params = {field: publication_id or slug}
    raw = await cache.get_or_compute(
        "publication_info",
        params,
        lambda: client.request("publication_info", params, tool_name="publication_info"),
    )
    return PublicationInfo.model_validate(raw)


async def publication_articles(
    *,
    settings: MediumSettings,
    dhara: DharaClient,
    cache: MediumCache,
    client: Medium2Client,
    publication_id: str,
    cursor: str | None = None,
) -> PublicationArticlesPage:
    params = {"publication_id": publication_id, "cursor": cursor}
    raw = await cache.get_or_compute(
        "publication_articles",
        params,
        lambda: client.request(
            "publication_articles", params, tool_name="publication_articles"
        ),
    )
    return PublicationArticlesPage.model_validate(raw)
