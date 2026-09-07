from __future__ import annotations

import pytest

from medium_mcp.tools.users import user_articles


async def test_user_articles_returns_page(stub_json, make_client) -> None:
    transport = stub_json(
        200,
        {
            "articles": [
                {
                    "id": "x",
                    "title": "T",
                    "author": "a",
                    "published_at": "2026-01-01T00:00:00Z",
                    "reading_time": 3,
                    "claps": 1,
                    "url": "https://medium.com/p/x",
                },
            ],
            "next_cursor": "page2",
        },
    )
    client, cache = make_client(transport)
    page = await user_articles(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
        user_id="abc",
    )
    assert page.next_cursor == "page2"
    assert len(page.articles) == 1
