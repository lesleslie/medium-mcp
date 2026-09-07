from __future__ import annotations

import json

import httpx2
import pytest
from pydantic import SecretStr

from medium_mcp.clients.medium2 import Medium2Client
from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient
from medium_mcp.dhara.keys import budget_key
from medium_mcp.utils.exceptions import (
    BudgetExhaustedError,
    ConfigurationError,
    NotFoundError,
    RateLimitedError,
    UpstreamError,
)


def _transport_that_returns(status: int, body: dict | str) -> httpx2.MockTransport:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if isinstance(body, dict):
            return httpx2.Response(status_code=status, json=body)
        return httpx2.Response(status_code=status, text=body)

    return httpx2.MockTransport(handler)


@pytest.fixture
def settings() -> MediumSettings:
    s = MediumSettings(_env_file=None)
    s.rapidapi_key = SecretStr("a" * 50)
    return s


@pytest.fixture
async def dhara(settings: MediumSettings) -> DharaClient:
    client = DharaClient(settings=settings, backend="memory")
    await client.startup()
    yield client
    await client.shutdown()


async def test_request_returns_json_on_200(settings: MediumSettings, dhara: DharaClient) -> None:
    transport = _transport_that_returns(200, {"id": "abc"})
    client = Medium2Client(settings=settings, dhara=dhara, transport=transport)
    result = await client.request("user_info", {"user_id": "abc"}, tool_name="user_info")
    assert result == {"id": "abc"}


async def test_request_404_raises_not_found(settings: MediumSettings, dhara: DharaClient) -> None:
    transport = _transport_that_returns(404, "")
    client = Medium2Client(settings=settings, dhara=dhara, transport=transport)
    with pytest.raises(NotFoundError):
        await client.request("user_info", {"user_id": "missing"}, tool_name="user_info")


async def test_request_429_raises_rate_limited(settings: MediumSettings, dhara: DharaClient) -> None:
    transport = _transport_that_returns(429, "")
    client = Medium2Client(settings=settings, dhara=dhara, transport=transport)
    with pytest.raises(RateLimitedError):
        await client.request("user_info", {"user_id": "abc"}, tool_name="user_info")


async def test_request_5xx_raises_upstream(settings: MediumSettings, dhara: DharaClient) -> None:
    transport = _transport_that_returns(500, "")
    client = Medium2Client(settings=settings, dhara=dhara, transport=transport)
    with pytest.raises(UpstreamError) as exc_info:
        await client.request("user_info", {"user_id": "abc"}, tool_name="user_info")
    assert exc_info.value.status_code == 500


async def test_request_increments_budget_on_success(
    settings: MediumSettings, dhara: DharaClient
) -> None:
    transport = _transport_that_returns(200, {"id": "abc"})
    client = Medium2Client(settings=settings, dhara=dhara, transport=transport)
    await client.request("user_info", {"user_id": "abc"}, tool_name="user_info")
    counter = await dhara.get_counter(f"medium2:v1:budget:2026-09")  # placeholder key
    # The exact period is computed; assert via the public ``budget_status`` accessor.
    status = await client.budget_status()
    assert status["calls_used"] >= 1


async def test_request_increments_budget_on_failure(
    settings: MediumSettings, dhara: DharaClient
) -> None:
    """Spec: failed calls count because RapidAPI's metering is undocumented."""
    transport = _transport_that_returns(500, "")
    client = Medium2Client(settings=settings, dhara=dhara, transport=transport)
    with pytest.raises(UpstreamError):
        await client.request("user_info", {"user_id": "abc"}, tool_name="user_info")
    status = await client.budget_status()
    assert status["calls_used"] >= 1


async def test_budget_exhausted_refuses_call(settings: MediumSettings, dhara: DharaClient) -> None:
    """monthly_budget=5, headroom=2 => ceiling 3. Exactly 3 calls get through."""
    settings.monthly_budget = 5
    settings.budget_reserve_headroom = 2
    transport = _transport_that_returns(200, {"id": "abc"})
    client = Medium2Client(settings=settings, dhara=dhara, transport=transport)
    refusals = 0
    successes = 0
    for _ in range(10):
        try:
            await client.request("user_info", {"user_id": "abc"}, tool_name="user_info")
            successes += 1
        except BudgetExhaustedError:
            refusals += 1
    assert successes == 3
    assert refusals == 7
    # A refused reservation must not have advanced the counter past the ceiling.
    assert await dhara.get_counter(budget_key(client.current_period())) == 3


async def test_headroom_check_happens_inside_the_lock(
    settings: MediumSettings, dhara: DharaClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ceiling is enforced by inc_atomic, not by a read-then-check in the client.

    If ``_reserve_budget`` peeked at the counter before locking, a caller could
    observe stale headroom. Assert the client delegates: it must pass the ceiling
    down as ``max_value`` and never pre-read the counter.
    """
    settings.monthly_budget = 5
    settings.budget_reserve_headroom = 2
    seen: list[dict[str, object]] = []

    async def fake_inc(key: str, **kwargs: object) -> tuple[int, bool]:
        # Stands in for the real lock-held read-check-increment-write, so the
        # real ``get_counter`` is never reached from inside the lock either.
        seen.append({"key": key, **kwargs})
        return 1, True

    def forbidden_counter(*_a: object, **_k: object) -> int:
        raise AssertionError("_reserve_budget must not read the counter outside the lock")

    monkeypatch.setattr(dhara, "inc_atomic", fake_inc)
    monkeypatch.setattr(dhara, "get_counter", forbidden_counter)

    transport = _transport_that_returns(200, {"id": "abc"})
    client = Medium2Client(settings=settings, dhara=dhara, transport=transport)
    await client.request("user_info", {"user_id": "abc"}, tool_name="user_info")

    # The ceiling is handed down as max_value; the client computed nothing else.
    assert seen == [
        {"key": budget_key(client.current_period()), "increment": 1, "max_value": 3},
    ]


async def test_dhara_down_refuses_before_reserving(
    settings: MediumSettings, dhara: DharaClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No counter, no guard: refuse rather than spend an unaccountable call."""

    async def probe_false() -> bool:
        return False

    monkeypatch.setattr(DharaClient, "probe", lambda _self: probe_false())
    transport = _transport_that_returns(200, {"id": "abc"})
    client = Medium2Client(settings=settings, dhara=dhara, transport=transport)
    with pytest.raises(UpstreamError) as exc_info:
        await client.request("user_info", {"user_id": "abc"}, tool_name="user_info")
    assert exc_info.value.context["reason"] == "dhara_unreachable"


async def test_max_pages_above_one_is_rejected(
    settings: MediumSettings, dhara: DharaClient
) -> None:
    """v1 reserves exactly one page per call; multi-page is not supported."""
    transport = _transport_that_returns(200, {"id": "abc"})
    client = Medium2Client(settings=settings, dhara=dhara, transport=transport)
    with pytest.raises(ConfigurationError):
        await client.request(
            "user_articles",
            {"user_id": "abc"},
            max_pages=3,
            tool_name="user_articles",
        )
