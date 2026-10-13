from __future__ import annotations

import asyncio
import time
from typing import Any

from medium_mcp.config.settings import MediumSettings
from medium_mcp.storage.in_memory_kv import AsyncKVStore
from medium_mcp.utils.exceptions import ConfigurationError
from medium_mcp.utils.in_process_lock import Lock

# How long a successful/failed ``probe()`` result stays warm.
PROBE_CACHE_SECONDS = 5.0


class DharaClient:
    """Wraps the in-process KV store and advisory lock for medium-mcp.

    The Dhara substrate was decommissioned (per `docs/plans/2026-09-16-dhara-mcp-retirement-plan.md`,
    status complete). medium-mcp migrates to substrate-agnostic primitives —
    ``medium_mcp.storage.in_memory_kv.AsyncKVStore`` (replaces the Dhara-backed
    ``AsyncMemoryStorage``+``AsyncConnection`` chain) and
    ``medium_mcp.utils.in_process_lock.Lock`` (replaces ``InMemoryDharaLock``).

    ``medium-mcp`` is a ``*-mcp`` repo (per `feedback-no-bodai-mentions-in-mcp-repos`)
    and cannot take a `mahavishnu` runtime dep, so the in-process ``Lock`` is a
    30-line local copy mirroring the ``mahavishnu.core._lock_sentinel.Lock``
    shape — see `feedback-substrate-compat-shim-rot.md`.

    Only the ``"memory"`` backend is supported; the ``"sql"``/``"postgres"``
    cross-process backends were also retired with the Dhara substrate (the
    ``memory`` backend was always the canonical choice for medium-mcp's per-
    process use case).
    """

    def __init__(self, settings: MediumSettings, backend: str = "memory") -> None:
        self.settings = settings
        self.backend = backend
        self._kv: AsyncKVStore | None = None
        self._lock: Lock | None = None
        self._started = False
        self._namespace = settings.dhara_namespace
        # ``probe()`` is on the hot path (every metered call gates on it), so its
        # result is cached for PROBE_CACHE_SECONDS.
        self._probe_cache_at: float = 0.0
        self._probe_cache_value: bool = False

    async def startup(self) -> None:
        if self._started:
            return
        if self.backend == "memory":
            self._kv = AsyncKVStore()
            self._lock = Lock()
        else:
            raise ConfigurationError(
                f"unknown backend {self.backend!r}; medium-mcp v1 supports 'memory' only",
                context={"backend": self.backend},
            )
        self._started = True

    async def shutdown(self) -> None:
        self._started = False
        self._kv = None
        self._lock = None
        # Invalidate the probe cache so a restarted client re-probes.
        self._probe_cache_at = 0.0
        self._probe_cache_value = False

    @property
    def kv(self) -> AsyncKVStore:
        if self._kv is None:
            raise RuntimeError("DharaClient.startup() not called")
        return self._kv

    @property
    def lock(self) -> Lock:
        if self._lock is None:
            raise RuntimeError("DharaClient.startup() not called")
        return self._lock

    async def probe(self) -> bool:
        """Round-trip a sentinel key to confirm the KV store is reachable.

        Result is cached for ``PROBE_CACHE_SECONDS`` because every metered call
        gates on this; without the cache a burst of tool calls would each pay a
        put+get round trip. ``shutdown()`` invalidates the cache.
        """
        if not self._started:
            return False
        now = time.monotonic()
        if now - self._probe_cache_at < PROBE_CACHE_SECONDS:
            return self._probe_cache_value
        sentinel_key = f"medium2:v1:probe:{self._namespace}"
        try:
            await self.kv.put_async(sentinel_key, b'"ok"', ttl=10)
            result = await self.kv.get_async(sentinel_key)
            probe_ok = result.get("value") == b'"ok"'
        except Exception:
            probe_ok = False
        self._probe_cache_at = now
        self._probe_cache_value = probe_ok
        return probe_ok

    async def get(self, key: str) -> bytes | None:
        result = await self.kv.get_async(key)
        return result.get("value")

    async def put(self, key: str, value: bytes, *, ttl: int | None = None) -> None:
        await self.kv.put_async(key, value, ttl=ttl)

    async def get_counter(self, key: str) -> int:
        raw = await self.get(key)
        if raw is None:
            return 0
        return int(raw.decode("utf-8"))

    async def inc_atomic(
        self,
        key: str,
        *,
        increment: int = 1,
        max_value: int | None = None,
    ) -> tuple[int, bool]:
        """Read-check-increment-write, entirely inside the per-period lock.

        Returns ``(counter_value, accepted)``.

        * accepted: the counter was advanced by ``increment`` and
          ``counter_value`` is the post-increment total.
        * refused: ``max_value`` was set and ``current + increment > max_value``.
          The counter is left **untouched** and ``counter_value`` is the
          unchanged current total.

        The check lives inside the lock so two concurrent reservations can never
        both observe the same headroom and both proceed. Callers translate a
        refusal into a domain error (``BudgetExhaustedError``); this layer knows
        nothing about budgets beyond the ceiling it was handed.
        """
        period = key.rsplit(":", 1)[-1]
        handle = await self.acquire_budget_lock(period)
        if handle is None:
            # Contention: yield briefly and retry once. If still busy, surface to caller.
            await asyncio.sleep(0.05)
            handle = await self.acquire_budget_lock(period)
        if handle is None:
            raise RuntimeError(f"could not acquire budget lock for {period}")
        try:
            current = await self.get_counter(key)
            if max_value is not None and current + increment > max_value:
                return current, False
            new_value = current + increment
            await self.put(key, str(new_value).encode())
            return new_value, True
        finally:
            await self.release_budget_lock(handle)

    async def dec_atomic(self, key: str, *, decrement: int) -> int:
        """Release a reservation under the same lock ``inc_atomic`` uses.

        Floors at zero: a double-release can never drive the counter negative
        and hand out budget that was never there.
        """
        if decrement <= 0:
            return await self.get_counter(key)
        period = key.rsplit(":", 1)[-1]
        handle = await self.acquire_budget_lock(period)
        if handle is None:
            await asyncio.sleep(0.05)
            handle = await self.acquire_budget_lock(period)
        if handle is None:
            raise RuntimeError(f"could not acquire budget lock for {period}")
        try:
            current = await self.get_counter(key)
            target = max(0, current - decrement)
            await self.put(key, str(target).encode())
            return target
        finally:
            await self.release_budget_lock(handle)

    async def acquire_budget_lock(self, period: str):
        key = f"medium2:v1:budget:lock:{period}"
        return self.lock.try_acquire(key, ttl_seconds=30)

    async def release_budget_lock(self, handle: Any) -> None:
        self.lock.release(handle)
