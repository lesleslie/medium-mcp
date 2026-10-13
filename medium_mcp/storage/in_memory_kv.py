from __future__ import annotations

import asyncio
from typing import Any


class AsyncKVStore:
    """Substrate-agnostic in-memory KV store for medium-mcp (replaces
    the Dhara-backed AsyncKVStore; the 'memory' backend was the only
    supported backend per the original DharaClient).
    """

    def __init__(self) -> None:
        self._items: dict[str, bytes] = {}
        self._lock = asyncio.Lock()

    async def put_async(self, key: str, value: bytes, *, ttl: int | None = None) -> None:
        """Store ``value`` under ``key``. TTL is a no-op for the in-process
        backend (medium-mcp config disables TTL in its current usage; verified
        pre-migration).
        """
        async with self._lock:
            self._items[key] = value

    async def get_async(self, key: str) -> dict[str, Any]:
        async with self._lock:
            value = self._items.get(key)
        return {"value": value}
