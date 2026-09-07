from __future__ import annotations

import pytest

from medium_mcp.tools.tags import tag_info, tag_latest


async def test_tag_info_returns_record(stub_json, make_client) -> None:
    transport = stub_json(
        200,
        {
            "tag": "python",
            "followers_count": 500,
            "related_tags": ["django", "fastapi"],
        },
    )
    client, cache = make_client(transport)
    result = await tag_info(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
        tag="python",
    )
    assert result.tag == "python"
    assert result.followers_count == 500


async def test_tag_latest_returns_page(stub_json, make_client) -> None:
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
            "next_cursor": None,
        },
    )
    client, cache = make_client(transport)
    page = await tag_latest(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
        tag="python",
    )
    assert page.next_cursor is None
    assert len(page.articles) == 1
