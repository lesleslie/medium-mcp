from __future__ import annotations

import pytest

from medium_mcp.tools.search import search_publications, search_users


async def test_search_users_returns_page(stub_json, make_client) -> None:
    transport = stub_json(
        200,
        {
            "users": [
                {
                    "id": "u1",
                    "username": "les",
                    "fullname": "Les Leslie",
                    "followers_count": 10,
                    "following_count": 5,
                    "bio": "writes code",
                    "twitter_username": "les",
                },
            ],
            "next_cursor": None,
        },
    )
    client, cache = make_client(transport)
    page = await search_users(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
        query="python",
    )
    assert page.next_cursor is None
    assert len(page.users) == 1


async def test_search_publications_returns_page(stub_json, make_client) -> None:
    transport = stub_json(
        200,
        {
            "publications": [
                {
                    "id": "p1",
                    "slug": "tldr",
                    "name": "TLDR",
                    "description": "tech",
                    "followers_count": 12345,
                    "url": "https://medium.com/tldr",
                },
            ],
            "next_cursor": None,
        },
    )
    client, cache = make_client(transport)
    page = await search_publications(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
        query="python",
    )
    assert page.next_cursor is None
    assert len(page.publications) == 1
