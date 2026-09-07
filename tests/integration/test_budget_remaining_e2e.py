from __future__ import annotations

from medium_mcp.tools.budget import budget_remaining


async def test_budget_remaining_returns_status(stub_json, make_client) -> None:
    client, cache = make_client(stub_json(200, {}))
    status = await budget_remaining(
        settings=client.settings,
        dhara=client.dhara,
        cache=cache,
        client=client,
    )
    assert status.remaining_calls == client.settings.monthly_budget
    assert status.monthly_budget == 150
    assert status.period.startswith("20")
