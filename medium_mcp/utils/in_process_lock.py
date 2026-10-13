from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class LockHandle:
    """Opaque token returned by ``Lock.try_acquire``; passes back to ``Lock.release``."""

    lock_key: str
    acquired_at: datetime  # UTC
    expires_at: datetime | None


class Lock:
    """Substrate-agnostic in-process lock for medium-mcp (mirrors
    mahavishnu.core._lock_sentinel.Lock's shape; see
    feedback-substrate-compat-shim-rot.md).

    NOTE: This is intentionally narrower than the sentinel. medium-mcp
    does not need owner_token, permanent, or metadata — its only call
    site is ``DharaClient.acquire_budget_lock`` which uses
    ``try_acquire(key, ttl_seconds=30)``. Adding dead parameters from
    the sentinel's full surface would be over-engineering.
    """

    def __init__(self) -> None:
        self._items: dict[str, LockHandle] = {}

    def try_acquire(self, lock_key: str, *, ttl_seconds: int | None = None) -> LockHandle | None:
        if lock_key in self._items:
            return None
        now = datetime.now(UTC)
        expires_at = None if ttl_seconds is None else now + timedelta(seconds=ttl_seconds)
        handle = LockHandle(lock_key=lock_key, acquired_at=now, expires_at=expires_at)
        self._items[lock_key] = handle
        return handle

    def release(self, handle: LockHandle) -> bool:
        if self._items.get(handle.lock_key) != handle:
            return False
        del self._items[handle.lock_key]
        return True
