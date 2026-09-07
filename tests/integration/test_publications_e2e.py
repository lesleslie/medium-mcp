from __future__ import annotations

import pytest

from medium_mcp.tools.publications import publication_articles, publication_info


async def test_publication_info_returns_record(stub_json, make_client) -> None:
    transport = stub_json(
        200,
        {
            "id": "p1",
            "slug": "tldr",
            "name": "TLDR",
            "description": "tech newsletter",
            "followers_count": 12345,
            "url": "https://medium.com/tldr",
        },
    )
    client, cache = make_client(transport)
    result = await publication_info(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
        slug="tldr",
    )
    assert result.slug == "tldr"
    assert result.followers_count == 12345


async def test_publication_info_requires_one_identifier(stub_json, make_client) -> None:
    from medium_mcp.utils.exceptions import ConfigurationError

    client, cache = make_client(stub_json(200, {}))
    with pytest.raises(ConfigurationError):
        await publication_info(
            settings=client.settings,
            dhara=client.dhara,
            cache=cache,
            client=client,
        )


async def test_publication_articles_returns_page(stub_json, make_client) -> None:
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
    page = await publication_articles(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
        publication_id="p1",
    )
    assert page.next_cursor is None
    assert len(page.articles) == 1
