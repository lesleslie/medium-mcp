from __future__ import annotations

import pytest

from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient


@pytest.fixture
def settings() -> MediumSettings:
    return MediumSettings(_env_file=None)


async def test_probe_succeeds_with_in_memory_backend(settings: MediumSettings) -> None:
    client = DharaClient(settings=settings, backend="memory")
    await client.startup()
    try:
        assert await client.probe() is True
    finally:
        await client.shutdown()


async def test_get_returns_none_for_missing_key(settings: MediumSettings) -> None:
    client = DharaClient(settings=settings, backend="memory")
    await client.startup()
    try:
        assert await client.get("medium2:v1:user_info:does-not-exist") is None
    finally:
        await client.shutdown()


async def test_put_then_get_round_trip(settings: MediumSettings) -> None:
    client = DharaClient(settings=settings, backend="memory")
    await client.startup()
    try:
        await client.put("medium2:v1:user_info:abc", b'{"id":"abc"}', ttl=60)
        assert await client.get("medium2:v1:user_info:abc") == b'{"id":"abc"}'
    finally:
        await client.shutdown()


async def test_inc_atomic(settings: MediumSettings) -> None:
    """Successive inc_atomic calls advance the counter from zero by ``increment``."""
    client = DharaClient(settings=settings, backend="memory")
    await client.startup()
    try:
        key = "medium2:v1:budget:2026-09"
        assert await client.inc_atomic(key) == (1, True)
        assert await client.inc_atomic(key, increment=2) == (3, True)
        assert await client.get_counter(key) == 3
    finally:
        await client.shutdown()


async def test_inc_atomic_refuses_past_max_value_without_mutating(
    settings: MediumSettings,
) -> None:
    """The ceiling check happens INSIDE the lock and leaves the counter alone."""
    client = DharaClient(settings=settings, backend="memory")
    await client.startup()
    try:
        key = "medium2:v1:budget:2026-09"
        assert await client.inc_atomic(key, increment=2, max_value=3) == (2, True)
        # 2 + 2 > 3 -> refused, counter unchanged at 2.
        assert await client.inc_atomic(key, increment=2, max_value=3) == (2, False)
        assert await client.get_counter(key) == 2
        # A smaller increment that still fits is accepted.
        assert await client.inc_atomic(key, increment=1, max_value=3) == (3, True)
    finally:
        await client.shutdown()


async def test_dec_atomic_floors_at_zero(settings: MediumSettings) -> None:
    client = DharaClient(settings=settings, backend="memory")
    await client.startup()
    try:
        key = "medium2:v1:budget:2026-09"
        await client.inc_atomic(key, increment=3)
        assert await client.dec_atomic(key, decrement=2) == 1
        assert await client.dec_atomic(key, decrement=99) == 0
    finally:
        await client.shutdown()


async def test_budget_lock_blocks_concurrent_holders(settings: MediumSettings) -> None:
    """Two workers cannot both hold the budget lock at the same time."""
    client = DharaClient(settings=settings, backend="memory")
    await client.startup()
    try:
        first = await client.acquire_budget_lock("2026-09")
        assert first is not None
        second = await client.acquire_budget_lock("2026-09")
        assert second is None  # contention: refused
        await client.release_budget_lock(first)
        third = await client.acquire_budget_lock("2026-09")
        assert third is not None
        await client.release_budget_lock(third)
    finally:
        await client.shutdown()
