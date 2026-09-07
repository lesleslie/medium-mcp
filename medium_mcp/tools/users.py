from __future__ import annotations

from typing import Any

from medium_mcp.cache.store import MediumCache
from medium_mcp.clients.medium2 import Medium2Client
from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient
from medium_mcp.models.dto import UserArticlesPage, UserInfo
from medium_mcp.utils.exceptions import ConfigurationError


async def _exactly_one(**kwargs: Any) -> str:
    provided = [k for k, v in kwargs.items() if v is not None]
    if len(provided) != 1:
        raise ConfigurationError(
            f"exactly one of {sorted(kwargs)} required, got {len(provided)}",
            context={"provided": provided},
        )
    return provided[0]


async def user_info(
    *,
    settings: MediumSettings,
    dhara: DharaClient,
    cache: MediumCache,
    client: Medium2Client,
    user_id: str | None = None,
    username: str | None = None,
) -> UserInfo:
    field = await _exactly_one(user_id=user_id, username=username)
    params = {field: locals()[field]}
    raw = await cache.get_or_compute(
        "user_info",
        params,
        lambda: client.request("user_info", params, tool_name="user_info"),
    )
    return UserInfo.model_validate(raw)


async def user_articles(
    *,
    settings: MediumSettings,
    dhara: DharaClient,
    cache: MediumCache,
    client: Medium2Client,
    user_id: str,
    cursor: str | None = None,
) -> UserArticlesPage:
    params = {"user_id": user_id, "cursor": cursor}
    raw = await cache.get_or_compute(
        "user_articles",
        params,
        lambda: client.request("user_articles", params, tool_name="user_articles"),
    )
    return UserArticlesPage.model_validate(raw)
