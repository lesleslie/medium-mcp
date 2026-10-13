from __future__ import annotations

import asyncio

from medium_mcp.storage.in_memory_kv import AsyncKVStore


async def test_put_then_get_round_trip() -> None:
    kv = AsyncKVStore()
    await kv.put_async("user_info:abc", b'{"id":"abc"}', ttl=60)
    result = await kv.get_async("user_info:abc")
    assert result["value"] == b'{"id":"abc"}'


async def test_get_missing_key_returns_empty_dict() -> None:
    kv = AsyncKVStore()
    result = await kv.get_async("does-not-exist")
    # New shim returns {"value": None}; the legacy Dhara shape added "ok"
    # and "key" fields — those are dropped because medium-mcp call sites
    # only ever read result["value"] (verified pre-migration).
    assert result == {"value": None}


async def test_concurrent_puts_are_serialized() -> None:
    kv = AsyncKVStore()
    n = 50

    async def put(i: int) -> None:
        await kv.put_async(f"k{i}", f"v{i}".encode(), ttl=None)

    await asyncio.gather(*(put(i) for i in range(n)))
    for i in range(n):
        result = await kv.get_async(f"k{i}")
        assert result["value"] == f"v{i}".encode(), f"lost update at k{i}"


async def test_put_is_isolated_between_instances() -> None:
    """Each AsyncKVStore is independent — no shared state across instances."""
    a = AsyncKVStore()
    b = AsyncKVStore()
    await a.put_async("k", b"A")
    await b.put_async("k", b"B")
    assert (await a.get_async("k"))["value"] == b"A"
    assert (await b.get_async("k"))["value"] == b"B"


async def test_ttl_is_a_noop() -> None:
    """The in-process backend ignores TTL; documented behavior."""
    kv = AsyncKVStore()
    await kv.put_async("k", b"v", ttl=0)
    assert (await kv.get_async("k"))["value"] == b"v"
