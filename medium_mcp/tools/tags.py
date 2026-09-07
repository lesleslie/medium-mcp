from __future__ import annotations

from medium_mcp.cache.store import MediumCache
from medium_mcp.clients.medium2 import Medium2Client
from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient
from medium_mcp.models.dto import TagInfo, TagLatestPage


async def tag_info(
    *,
    settings: MediumSettings,
    dhara: DharaClient,
    cache: MediumCache,
    client: Medium2Client,
    tag: str,
) -> TagInfo:
    params = {"tag": tag}
    raw = await cache.get_or_compute(
        "tag_info",
        params,
        lambda: client.request("tag_info", params, tool_name="tag_info"),
    )
    return TagInfo.model_validate(raw)


async def tag_latest(
    *,
    settings: MediumSettings,
    dhara: DharaClient,
    cache: MediumCache,
    client: Medium2Client,
    tag: str,
    cursor: str | None = None,
) -> TagLatestPage:
    params = {"tag": tag, "cursor": cursor}
    raw = await cache.get_or_compute(
        "tag_latest",
        params,
        lambda: client.request("tag_latest", params, tool_name="tag_latest"),
    )
    return TagLatestPage.model_validate(raw)
