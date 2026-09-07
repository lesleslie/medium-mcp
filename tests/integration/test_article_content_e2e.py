from __future__ import annotations

import httpx2
import pytest

from medium_mcp.tools.articles import article_content


_METADATA_BODY = {
    "id": "abc",
    "title": "T",
    "author": "a",
    "published_at": "2026-01-01T00:00:00Z",
    "reading_time": 3,
    "claps": 1,
    "voters": 0,
    "tags": [],
    "url": "https://medium.com/p/abc",
    "excerpt": "excerpt text",
}


async def test_article_content_without_flag_returns_no_full_text(stub_json, make_client) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if "article_metadata" in str(request.url):
            return httpx2.Response(200, json=_METADATA_BODY)
        return httpx2.Response(200, json={"content": {"body": "secret text"}})

    transport = httpx2.MockTransport(handler)
    client, cache = make_client(transport)
    result = await article_content(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
        article_id="abc",
        include_full_text=False,
    )
    assert result.full_text is None


async def test_article_content_with_flag_returns_full_text(stub_json, make_client) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if "article_metadata" in str(request.url):
            return httpx2.Response(200, json=_METADATA_BODY)
        return httpx2.Response(200, json={"content": {"body": "secret text"}})

    transport = httpx2.MockTransport(handler)
    client, cache = make_client(transport)
    result = await article_content(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
        article_id="abc",
        include_full_text=True,
    )
    assert result.full_text == "secret text"
