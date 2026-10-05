"""Minimal async KV store with TTL — a stand-in for the deleted ``dhara.mcp.kv_timeseries``.

dhara's Wave-2 cleanup (commit 71697e1) deleted ``dhara.mcp.kv_timeseries``. medium-mcp
only ever used the put/get surface, not the time-series methods, so we inline a small
KV+TTL class here backed by ``AsyncConnection`` rather than reintroduce the deleted
module. The interface mirrors the original ``AsyncKVTimeSeriesStore`` shape (``put_async``
returns ``{"ok": True, "key": key}``; ``get_async`` returns a dict with ``"value"``)
so existing call sites in :mod:`medium_mcp.dhara.client` keep working unchanged.
"""

from __future__ import annotations

import time
from typing import Any

from dhara.collections.dict import PersistentDict
from dhara.core.connection import AsyncConnection


class AsyncKVStore:
    """Async Dhara-backed key/value store with optional TTL.

    TTL is tracked in a sibling ``PersistentDict`` keyed by the same string;
    expired keys are pruned on read. The store is initialised lazily on the
    first call so an unstarted instance never touches the connection root.
    """

    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection
        self._initialized = False

    async def _ensure_root_async(self) -> None:
        if self._initialized:
            return
        root = await self.connection.get_root()
        changed = False
        if "kv" not in root:
            root["kv"] = PersistentDict()
            changed = True
        if "kv_ttl" not in root:
            root["kv_ttl"] = PersistentDict()
            changed = True
        if changed:
            await self.connection.commit()
        self._initialized = True

    async def _kv(self) -> PersistentDict:
        root = await self.connection.get_root()
        return root["kv"]  # type: ignore[no-any-return]

    async def _kv_ttl(self) -> PersistentDict:
        root = await self.connection.get_root()
        return root["kv_ttl"]  # type: ignore[no-any-return]

    async def put_async(
        self, key: str, value: Any, ttl: int | None = None
    ) -> dict[str, Any]:
        await self._ensure_root_async()
        kv = await self._kv()
        ttl_map = await self._kv_ttl()

        kv[key] = value
        if ttl is not None:
            ttl_map[key] = int(time.time()) + int(ttl)
        elif key in ttl_map:
            del ttl_map[key]

        await self.connection.commit()
        return {"ok": True, "key": key}

    async def get_async(self, key: str) -> dict[str, Any]:
        await self._ensure_root_async()
        kv = await self._kv()
        ttl_map = await self._kv_ttl()

        if key not in kv:
            return {"ok": True, "key": key, "value": None}

        expires_at = ttl_map.get(key)
        if expires_at and int(time.time()) >= int(expires_at):
            del kv[key]
            del ttl_map[key]
            await self.connection.commit()
            return {"ok": True, "key": key, "value": None, "expired": True}

        return {"ok": True, "key": key, "value": kv[key]}