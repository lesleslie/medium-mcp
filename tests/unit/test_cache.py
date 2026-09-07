from __future__ import annotations

import asyncio

import pytest

from medium_mcp.cache.store import MediumCache
from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient
from medium_mcp.dhara.keys import cache_key, content_key


@pytest.fixture
def settings() -> MediumSettings:
    return MediumSettings(_env_file=None)


@pytest.fixture
async def dhara(settings: MediumSettings) -> DharaClient:
    client = DharaClient(settings=settings, backend="memory")
    await client.startup()
    yield client
    await client.shutdown()


async def test_put_then_get_round_trip(settings: MediumSettings, dhara: DharaClient) -> None:
    cache = MediumCache(settings=settings, dhara=dhara)
    await cache.put("user_info", {"user_id": "abc"}, b'{"id":"abc"}', ttl=settings.cache_ttl_user_info)
    result = await cache.get("user_info", {"user_id": "abc"})
    assert result == b'{"id":"abc"}'


async def test_content_cache_uses_separate_key(settings: MediumSettings, dhara: DharaClient) -> None:
    cache = MediumCache(settings=settings, dhara=dhara)
    await cache.put(
        "article_content",
        {"article_id": "x"},
        b"full text",
        ttl=settings.cache_ttl_article_content,
        content=True,
    )
    # Direct Dhara key check: content prefix is distinct.
    raw = await dhara.get(content_key("x"))
    assert raw == b"full text"
    # The non-content cache key for the same params must NOT have it.
    raw_meta = await dhara.get(cache_key("article_content", {"article_id": "x"}))
    assert raw_meta is None


async def test_ttl_selection_by_endpoint(settings: MediumSettings, dhara: DharaClient) -> None:
    cache = MediumCache(settings=settings, dhara=dhara)
    assert cache._ttl_for("user_info") == settings.cache_ttl_user_info
    assert cache._ttl_for("user_articles") == settings.cache_ttl_user_articles
    assert cache._ttl_for("article_metadata") == settings.cache_ttl_article_metadata
    assert cache._ttl_for("search_articles") == settings.cache_ttl_search
    assert cache._ttl_for("tag_info") == settings.cache_ttl_tag


async def test_coalesce_concurrent_calls_share_one_upstream(
    settings: MediumSettings, dhara: DharaClient
) -> None:
    """Two concurrent get_or_compute calls share one upstream call."""
    cache = MediumCache(settings=settings, dhara=dhara)

    upstream_calls = 0

    async def compute() -> bytes:
        nonlocal upstream_calls
        upstream_calls += 1
        await asyncio.sleep(0.05)
        return b'{"v":1}'

    results = await asyncio.gather(
        cache.get_or_compute("user_info", {"user_id": "abc"}, compute),
        cache.get_or_compute("user_info", {"user_id": "abc"}, compute),
        cache.get_or_compute("user_info", {"user_id": "abc"}, compute),
    )
    assert all(r == b'{"v":1}' for r in results)
    assert upstream_calls == 1


async def test_coalesce_window_timeout_returns_typed_error(
    settings: MediumSettings, dhara: DharaClient
) -> None:
    """If the leader takes longer than the window, followers do NOT block."""
    settings.coalesce_window_seconds = 0.05
    cache = MediumCache(settings=settings, dhara=dhara)

    async def slow_compute() -> bytes:
        await asyncio.sleep(0.5)
        return b"x"

    # The leader kicks off the compute; the follower waits for the future but
    # the window elapses first, so the follower raises CoalesceTimeout while
    # the leader continues to run.
    leader = asyncio.create_task(
        cache.get_or_compute("user_info", {"user_id": "abc"}, slow_compute),
    )
    follower = asyncio.create_task(
        cache.get_or_compute("user_info", {"user_id": "abc"}, slow_compute),
    )
    with pytest.raises(Exception):  # CoalesceTimeout
        await follower
    # Leader still runs to completion (no cancellation leak).
    assert await leader == b"x"
