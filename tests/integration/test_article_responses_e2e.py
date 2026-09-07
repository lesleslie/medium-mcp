from __future__ import annotations

import pytest

from medium_mcp.tools.articles import article_responses


async def test_article_responses_returns_page(stub_json, make_client) -> None:
    transport = stub_json(
        200,
        {
            "articles": [
                {
                    "id": "r1",
                    "title": "Reply",
                    "author": "b",
                    "published_at": "2026-01-01T00:00:00Z",
                    "reading_time": 1,
                    "claps": 0,
                    "url": "https://medium.com/p/r1",
                },
            ],
            "next_cursor": None,
        },
    )
    client, cache = make_client(transport)
    page = await article_responses(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
        article_id="abc",
    )
    assert page.next_cursor is None
    assert len(page.articles) == 1
