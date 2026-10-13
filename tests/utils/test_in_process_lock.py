from __future__ import annotations

from datetime import UTC

from medium_mcp.utils.in_process_lock import Lock, LockHandle


def test_try_acquire_returns_handle_on_first_call() -> None:
    lock = Lock()
    handle = lock.try_acquire("budget:2026-09", ttl_seconds=30)
    assert isinstance(handle, LockHandle)
    assert handle.lock_key == "budget:2026-09"
    assert handle.acquired_at.tzinfo is not None
    assert handle.acquired_at.tzinfo == UTC
    assert handle.expires_at is not None


def test_try_acquire_returns_none_on_contention() -> None:
    lock = Lock()
    first = lock.try_acquire("budget:2026-09", ttl_seconds=30)
    assert first is not None
    second = lock.try_acquire("budget:2026-09", ttl_seconds=30)
    assert second is None


def test_release_clears_the_lock() -> None:
    lock = Lock()
    handle = lock.try_acquire("budget:2026-09", ttl_seconds=30)
    assert handle is not None
    assert lock.release(handle) is True
    second = lock.try_acquire("budget:2026-09", ttl_seconds=30)
    assert second is not None
    assert second.acquired_at >= handle.acquired_at


def test_release_returns_false_for_stale_handle() -> None:
    lock = Lock()
    handle = lock.try_acquire("budget:2026-09", ttl_seconds=30)
    assert handle is not None
    assert lock.release(handle) is True
    # Released once → second release with the same handle must report False.
    assert lock.release(handle) is False


def test_try_acquire_without_ttl_has_no_expiry() -> None:
    lock = Lock()
    handle = lock.try_acquire("k")
    assert handle is not None
    assert handle.expires_at is None


def test_release_returns_false_for_unknown_key() -> None:
    lock = Lock()
    other = LockHandle(
        lock_key="never-acquired",
        acquired_at=__import__("datetime").datetime.now(UTC),
        expires_at=None,
    )
    assert lock.release(other) is False
