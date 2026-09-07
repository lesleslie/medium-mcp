from __future__ import annotations

from medium_mcp.tools.users import user_info


async def test_user_info_returns_real_user(stub_json, make_client) -> None:
    transport = stub_json(
        200,
        {
            "id": "1a2b",
            "username": "les",
            "fullname": "Les Leslie",
            "followers_count": 42,
            "following_count": 7,
            "bio": "writes code",
            "twitter_username": "les",
        },
    )
    client, cache = make_client(transport)
    result = await user_info(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
        user_id="1a2b",
    )
    assert result.user_id == "1a2b"
    assert result.username == "les"
    assert result.followers_count == 42
