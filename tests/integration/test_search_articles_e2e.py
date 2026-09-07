from __future__ import annotations

from medium_mcp.tools.search import search_articles


async def test_search_articles_returns_page(stub_json, make_client) -> None:
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
            "next_cursor": "nextpage",
        },
    )
    client, cache = make_client(transport)
    page = await search_articles(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
        query="python",
    )
    assert page.next_cursor == "nextpage"
    assert len(page.articles) == 1
    assert page.articles[0].article_id == "x"
