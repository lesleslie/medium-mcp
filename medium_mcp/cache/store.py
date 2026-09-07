from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient
from medium_mcp.dhara.keys import cache_key, coalesce_key, content_key
from medium_mcp.utils.exceptions import MediumError


class CoalesceTimeout(MediumError):
    """The leader's compute exceeded the coalesce window; follower gives up."""


_TTL_TABLE = {
    "user_info": "cache_ttl_user_info",
    "user_articles": "cache_ttl_user_articles",
    "article_metadata": "cache_ttl_article_metadata",
    "article_content": "cache_ttl_article_content",
    "search_articles": "cache_ttl_search",
    "search_users": "cache_ttl_search",
    "search_publications": "cache_ttl_search",
    "tag_info": "cache_ttl_tag",
    "tag_latest": "cache_ttl_tag",
    "publication_info": "cache_ttl_user_info",
    "publication_articles": "cache_ttl_user_articles",
}


class MediumCache:
    """Two keyspaces: metadata cache (``medium2:v1:<endpoint>:...``) and
    content cache (``medium2:v1:content:<article_id>``). Coalesces concurrent
    ``get_or_compute`` callers via an in-process future registry.
    """

    def __init__(
        self,
        *,
        settings: MediumSettings,
        dhara: DharaClient,
    ) -> None:
        self.settings = settings
        self.dhara = dhara
        self._in_flight: dict[str, asyncio.Future[bytes]] = {}

    def _ttl_for(self, endpoint: str) -> int:
        attr = _TTL_TABLE.get(endpoint)
        if attr is None:
            return self.settings.cache_ttl_search  # conservative default
        return getattr(self.settings, attr)

    async def get(self, endpoint: str, params: dict[str, Any], *, content: bool = False) -> bytes | None:
        if content:
            article_id = params.get("article_id", "")
            return await self.dhara.get(content_key(article_id))
        return await self.dhara.get(cache_key(endpoint, params))

    async def put(
        self,
        endpoint: str,
        params: dict[str, Any],
        value: bytes,
        *,
        ttl: int,
        content: bool = False,
    ) -> None:
        if content:
            article_id = params.get("article_id", "")
            await self.dhara.put(content_key(article_id), value, ttl=ttl)
            return
        await self.dhara.put(cache_key(endpoint, params), value, ttl=ttl)

    async def get_or_compute(
        self,
        endpoint: str,
        params: dict[str, Any],
        compute_fn: Callable[[], Awaitable[bytes]],
    ) -> bytes:
        cached = await self.get(endpoint, params)
        if cached is not None:
            return cached

        key = coalesce_key(endpoint, params)
        loop = asyncio.get_running_loop()
        if key in self._in_flight:
            # Follower: wait on the leader's future with a bounded timeout.
            fut = self._in_flight[key]
            try:
                return await asyncio.wait_for(fut, timeout=self.settings.coalesce_window_seconds)
            except asyncio.TimeoutError as exc:
                raise CoalesceTimeout(
                    "coalesce window elapsed waiting for leader",
                    context={"key": key, "window": self.settings.coalesce_window_seconds},
                ) from exc

        # Leader: install a future and run the compute.
        fut = loop.create_future()
        self._in_flight[key] = fut
        try:
            value = await compute_fn()
            await self.put(endpoint, params, value, ttl=self._ttl_for(endpoint))
            if not fut.done():
                fut.set_result(value)
            return value
        except BaseException as exc:
            if not fut.done():
                fut.set_exception(exc)
            raise
        finally:
            self._in_flight.pop(key, None)
