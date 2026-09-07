from __future__ import annotations

import pytest
from pydantic import SecretStr

from medium_mcp.cache.store import MediumCache
from medium_mcp.clients.medium2 import Medium2Client
from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient
from medium_mcp.tools.articles import (
    article_content,
    article_metadata,
    article_responses,
)
from medium_mcp.tools.budget import budget_remaining
from medium_mcp.tools.publications import publication_articles, publication_info
from medium_mcp.tools.search import search_articles, search_publications, search_users
from medium_mcp.tools.tags import tag_info, tag_latest
from medium_mcp.tools.users import user_articles, user_info
from medium_mcp.utils.exceptions import ConfigurationError


@pytest.fixture
def settings() -> MediumSettings:
    s = MediumSettings(_env_file=None)
    s.rapidapi_key = SecretStr("a" * 50)
    return s


@pytest.fixture
async def dhara(settings: MediumSettings) -> DharaClient:
    c = DharaClient(settings=settings, backend="memory")
    await c.startup()
    yield c
    await c.shutdown()


async def test_user_info_requires_exactly_one_identifier(settings: MediumSettings) -> None:
    with pytest.raises(ConfigurationError):
        await user_info(settings=None, dhara=None, cache=None, client=None)  # type: ignore[arg-type]


async def test_article_content_returns_none_when_flag_false(
    settings: MediumSettings, dhara: DharaClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §6.2 rule 3: return is gated independently of cache state."""
    # Pre-populate the content cache with a full body.
    await dhara.put("medium2:v1:content:abc", b"the actual article body", ttl=99999)

    client = Medium2Client(settings=settings, dhara=dhara)

    # article_metadata must succeed; article_content must NOT be called
    # because include_full_text=False short-circuits at the tool layer.
    called: list[str] = []

    async def fake_request(endpoint: str, params, **kwargs):
        called.append(endpoint)
        if endpoint == "article_metadata":
            return {
                "id": params["article_id"],
                "title": "T",
                "author": "a",
                "published_at": "2026-01-01T00:00:00Z",
                "reading_time": 3,
                "claps": 1,
                "voters": 0,
                "tags": [],
                "url": "https://medium.com/p/abc",
                "excerpt": "first excerpt",
            }
        if endpoint == "article_content":
            return {"content": {"body": "should not be returned"}}
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    monkeypatch.setattr(client, "request", fake_request)

    cache = MediumCache(settings=settings, dhara=dhara)
    result = await article_content(
        settings=settings,
        dhara=dhara,
        cache=cache,
        client=client,
        article_id="abc",
        include_full_text=False,
        format="markdown",
    )
    # Even though the cache has the body, the tool must NOT return it.
    assert result.full_text is None
    assert result.include_full_text is False
    assert called == ["article_metadata"]


async def test_article_content_returns_full_text_when_flag_true(
    settings: MediumSettings, dhara: DharaClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await dhara.put("medium2:v1:content:abc", b"the actual article body", ttl=99999)

    client = Medium2Client(settings=settings, dhara=dhara)
    cache = MediumCache(settings=settings, dhara=dhara)

    async def fake_request(endpoint: str, params, **kwargs):
        if endpoint == "article_metadata":
            return {
                "id": params["article_id"],
                "title": "T",
                "author": "a",
                "published_at": "2026-01-01T00:00:00Z",
                "reading_time": 3,
                "claps": 1,
                "voters": 0,
                "tags": [],
                "url": "https://medium.com/p/abc",
                "excerpt": "first excerpt",
            }
        if endpoint == "article_content":
            return {"content": {"body": "the actual article body"}}
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    monkeypatch.setattr(client, "request", fake_request)

    result = await article_content(
        settings=settings,
        dhara=dhara,
        cache=cache,
        client=client,
        article_id="abc",
        include_full_text=True,
        format="markdown",
    )
    assert result.full_text == "the actual article body"
    assert result.include_full_text is True


async def test_budget_remaining_makes_no_upstream_call(
    settings: MediumSettings, dhara: DharaClient
) -> None:
    """budget_remaining must be a local read; spec §6.2."""
    client = Medium2Client(settings=settings, dhara=dhara)

    class Guard:
        async def request(self, *args, **kwargs):
            raise AssertionError("upstream must not be called for budget_remaining")

    cache = MediumCache(settings=settings, dhara=dhara)
    status = await budget_remaining(
        settings=settings, dhara=dhara, cache=cache, client=client
    )
    assert status.remaining_calls == settings.monthly_budget
    assert status.monthly_budget == 150


async def test_tools_reject_malformed_inputs(settings: MediumSettings) -> None:
    """user_info with neither user_id nor username raises ConfigurationError."""
    dhara = None
    cache = None
    client = None
    with pytest.raises(Exception):
        await user_info(settings=settings, dhara=dhara, cache=cache, client=client)
