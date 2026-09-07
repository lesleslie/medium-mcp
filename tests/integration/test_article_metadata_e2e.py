from __future__ import annotations

import pytest

from medium_mcp.tools.articles import article_metadata


async def test_article_metadata_returns_full_record(stub_json, make_client) -> None:
    transport = stub_json(
        200,
        {
            "id": "abc",
            "title": "Hello",
            "subtitle": "world",
            "author": "1a2b",
            "published_at": "2026-08-01T00:00:00Z",
            "reading_time": 5,
            "claps": 100,
            "voters": 30,
            "tags": ["python", "mcp"],
            "url": "https://medium.com/p/abc",
            "excerpt": "first 200 chars",
        },
    )
    client, cache = make_client(transport)
    result = await article_metadata(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
        article_id="abc",
    )
    assert result.article_id == "abc"
    assert result.title == "Hello"
    assert result.tags == ["python", "mcp"]
    assert result.excerpt == "first 200 chars"
