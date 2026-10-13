---
status: active
role: implementation
kind: plan
date: 2026-10-13
last_reviewed: 2026-10-13
superseded_by: null
blocks_on: []
# Sequencing note: this plan must land BEFORE
# `docs/plans/2026-10-12-dhara-lock-delete.md` (in the mahavishnu repo)
# Phase 1.5 — the dhara delete is sequenced behind this migration.
# If this plan's `git push` happens after the dhara delete, the imports
# in `medium_mcp/dhara/{client,kv_store}.py` will break at module load.
# The recommended order is: this plan lands → dhara delete lands.
topic: medium-mcp-migrate-off-dhara
title: "Migrate medium-mcp off obsolete Dhara substrate (5 imports across 2 files)"
---

# Migrate `medium-mcp` off the obsolete Dhara substrate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove **5 Dhara substrate imports across 2 files** in `medium-mcp` (3 in `medium_mcp/dhara/client.py` + 2 in `medium_mcp/dhara/kv_store.py`) and replace them with substrate-agnostic in-process primitives — a minimal lock shim and an in-memory KV-store shim, both living in `medium_mcp/utils/` and `medium_mcp/storage/`. After this lands, `rg -n 'from dhara\|import dhara' /Users/les/Projects/medium-mcp/medium_mcp/ --type py` returns 0 hits and the `2026-10-12-dhara-lock-delete.md` plan can safely delete `dhara/dhara/lock/`. Per `feedback-substrate-compat-shim-rot.md`: the Dhara substrate was decommissioned (see `docs/plans/2026-09-16-dhara-mcp-retirement-plan.md` status: complete); the lock primitive was re-homed to `mahavishnu.core._lock_sentinel.Lock` for substrate-agnostic coordination, but `medium-mcp` is a `*-mcp` repo (per `feedback-no-bodai-mentions-in-mcp-repos`) and cannot take a new `mahavishnu` runtime dep without violating the rule. The right primitive for `medium-mcp` is its own in-process local copy.

**The 5 Dhara imports to remove (verified 2026-10-13 via `rg`):**

| File | Line | Import |
|---|---|---|
| `medium_mcp/dhara/client.py` | 7 | `from dhara.lock.in_memory import InMemoryDharaLock` |
| `medium_mcp/dhara/client.py` | 41 | `from dhara.core.connection import AsyncConnection` |
| `medium_mcp/dhara/client.py` | 42 | `from dhara.storage.memory import AsyncMemoryStorage` |
| `medium_mcp/dhara/kv_store.py` | 16 | `from dhara.collections.dict import PersistentDict` |
| `medium_mcp/dhara/kv_store.py` | 17 | `from dhara.core.connection import AsyncConnection` |

The `kv_store.py` file was missed in the original draft of this plan; the 2 missing imports were caught by the re-review pass (mcp-integration-expert, 2026-10-13). Without this correction the Phase 3 acceptance criterion ("rg returns 0 hits") would be unreachable — `kv_store.py` would still import `PersistentDict` and `AsyncConnection`.

**Architecture (option a from the re-review, picked for the cleanest substrate-agnostic result):**
- **Drop the `medium_mcp/dhara/` directory entirely.** The `DharaClient` class moves to `medium_mcp/storage/dhara_client.py`; the `AsyncKVStore` class moves to `medium_mcp/storage/in_memory_kv.py`. The `DharaClient` *class name* is preserved (it's the local API surface used by `medium_mcp/dhara/__init__.py` callers and by tests); the *file path* drops the `dhara/` directory.
- **New `medium_mcp/utils/in_process_lock.py`** — a 30-line `Lock` class with the minimum surface the call sites actually use: `try_acquire(key, *, ttl_seconds=None) -> LockHandle | None` and `release(handle) -> bool`. No `owner_token` / `permanent` / `metadata` parameters (the call site `client.py:176` only uses `try_acquire(key, ttl_seconds=30)`; the sentinel's full surface is dead complexity for medium-mcp's per-process use case).
- **New `medium_mcp/storage/in_memory_kv.py`** — an `AsyncKVStore` class with the minimum surface the call site uses: `put_async(key, value: bytes, *, ttl: int | None = None)` and `get_async(key) -> dict`. The `connection` parameter is dropped (the in-memory backend doesn't need it). The existing `AsyncKVStore` at `medium_mcp/dhara/kv_store.py:28` had `def __init__(self, connection: AsyncConnection)`; the new shim is no-args (matches the planned `client.py:46` call `self._kv = AsyncKVStore()`).
- **The 5 Dhara imports disappear**; the `medium_mcp/dhara/` directory is removed; the `DharaClient` class lives in `medium_mcp/storage/dhara_client.py`.

**Why not import from `mahavishnu.core._lock_sentinel.Lock`?** That sentinel is the canonical substrate-agnostic home for in-process coordination across the Bodai core (mahavishnu, akosha, session-buddy, crackerjack, mcp-common, oneiric). `medium-mcp` is a `*-mcp` repo — per `feedback-no-bodai-mentions-in-mcp-repos`, `*-mcp` repos "are managed by Bodai but NOT part of the ecosystem" and cannot take ecosystem-component runtime deps. Adding a `mahavishnu` dep to `medium-mcp`'s `pyproject.toml` would violate the rule. The right primitive is a 30-line local copy that mirrors the sentinel's shape.

**Tech Stack:** Python 3.14, asyncio (stdlib), no new dependencies.

## Global Constraints

- `from __future__ import annotations` first non-comment line of every new module.
- Ruff line length 100; per-file ignores in `pyproject.toml` apply unchanged.
- mypy strict; `X | None` (not `Optional[X]`), `list[str]` (not `List[str]`), `pathlib.Path`.
- Function args ≤ 10 (excluding `self`/`cls`/`*args`/`**kwargs`).
- No `assert` in production code (`medium_mcp/**`).
- In `except` blocks, use `logger.exception(...)`, never `logger.error(..., exc_info=True)`.
- Remove unused imports and dead code immediately (Ruff F401 / UP).
- No `Co-Authored-By` trailer in commit message (per `feedback-no-claude-code-coauthor-attribution.md`).
- Use `user.email="les@wedgwoodwebworks.com"` for any commits.

## Phase 1 — Inventory the Dhara footprint (5 imports, 2 files)

- [ ] Run `rg -n 'from dhara\|import dhara' /Users/les/Projects/medium-mcp/medium_mcp/ --type py` and capture the full hit list. Expected: **5 hits** — `medium_mcp/dhara/client.py:7` (`InMemoryDharaLock`), `medium_mcp/dhara/client.py:41` (`AsyncConnection`), `medium_mcp/dhara/client.py:42` (`AsyncMemoryStorage`), `medium_mcp/dhara/kv_store.py:16` (`PersistentDict`), `medium_mcp/dhara/kv_store.py:17` (`AsyncConnection`).
- [ ] Confirm the `medium_mcp/dhara/__init__.py` exists and re-exports `DharaClient` (so the file path move doesn't break other call sites). If the `__init__.py` re-exports anything from `kv_store.py`, that needs to be updated too.
- [ ] Run `rg -n 'from medium_mcp.dhara\|import medium_mcp.dhara' /Users/les/Projects/medium-mcp/ --type py` to find all internal callers of the old `medium_mcp/dhara/` namespace. The migration needs to update every caller.
- [ ] Run `pytest medium-mcp/ -v --no-cov` to establish the pre-migration baseline (all tests green).

#### Integration Contract ← REQUIRED
- **Triggered from**: developer / agent running the inventory before adding the new modules.
- **Returns to / updates**: nothing persisted; a captured baseline of the 5 Dhara call sites + the list of internal callers of `medium_mcp.dhara.*`.
- **Demonstrable by**: the rg output matches the expected 5 hits; the internal-caller list is captured; `pytest` exits 0.
- **Rollback signal**: not applicable — Phase 1 is read-only.
- **Observability added**: none.

## Phase 2 — Add the substrate-agnostic primitives

- [ ] Create `medium_mcp/utils/in_process_lock.py` with `from __future__ import annotations` as the first non-comment line. Define a `Lock` class with **only the minimum surface the call sites use**:
  ```python
  @dataclass(frozen=True)
  class LockHandle:
      lock_key: str
      acquired_at: datetime  # UTC
      expires_at: datetime | None

  class Lock:
      """Substrate-agnostic in-process lock for medium-mcp (mirrors
      mahavishnu.core._lock_sentinel.Lock's shape; see
      feedback-substrate-compat-shim-rot.md).

      NOTE: This is intentionally narrower than the sentinel. medium-mcp
      does not need owner_token, permanent, or metadata — its only call
      site is `DharaClient.acquire_budget_lock` which uses
      `try_acquire(key, ttl_seconds=30)`. Adding dead parameters from
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
  ```
- [ ] Add unit tests in `medium-mcp/tests/utils/test_in_process_lock.py`:
  - `test_try_acquire_returns_handle_on_first_call` — `try_acquire("k", ttl_seconds=30)` returns a `LockHandle`.
  - `test_try_acquire_returns_none_on_contention` — second call with same key returns `None`.
  - `test_release_clears_the_lock` — `release(handle)` then `try_acquire` again succeeds.
  - `test_release_returns_false_for_stale_handle` — release with a handle whose key was already released returns `False`.
- [ ] Create `medium_mcp/storage/in_memory_kv.py` with `from __future__ import annotations` as the first non-comment line. Define an `AsyncKVStore` class with the **no-args constructor** (the existing `AsyncKVStore(connection: AsyncConnection)` signature is dropped; the new shim is in-memory only):
  ```python
  class AsyncKVStore:
      """Substrate-agnostic in-memory KV store for medium-mcp (replaces
      the Dhara-backed AsyncKVStore; the 'memory' backend was the only
      supported backend per the original DharaClient).
      """
      def __init__(self) -> None:
          self._items: dict[str, bytes] = {}
          self._lock = asyncio.Lock()
      async def put_async(self, key: str, value: bytes, *, ttl: int | None = None) -> None:
          # TTL is a no-op for the in-process backend (medium-mcp config
          # disables TTL in its current usage; verified pre-migration).
          async with self._lock:
              self._items[key] = value
      async def get_async(self, key: str) -> dict[str, Any]:
          async with self._lock:
              value = self._items.get(key)
          return {"value": value}
  ```
- [ ] Add unit tests in `medium-mcp/tests/storage/test_in_memory_kv.py`:
  - `test_put_then_get_round_trip`
  - `test_get_missing_key_returns_empty_dict`
  - `test_concurrent_puts_are_serialized` (`asyncio.gather` with N concurrent put_async calls; final state has all N keys; no lost updates).

#### Integration Contract ← REQUIRED
- **Triggered from**: developer / agent reading the call sites in `client.py:174-179` (the only consumer) and writing the shims.
- **Returns to / updates**: 2 new modules in `medium_mcp/utils/` and `medium_mcp/storage/`, with passing unit tests.
- **Demonstrable by**: `pytest medium-mcp/tests/utils/test_in_process_lock.py medium-mcp/tests/storage/test_in_memory_kv.py -v --no-cov` shows all tests green.
- **Rollback signal**: a unit test in the new modules fails for ≥1 commit after merge.
- **Observability added**: none.

## Phase 3 — Migrate `DharaClient` to the new primitives

- [ ] **Move** `medium_mcp/dhara/client.py` to `medium_mcp/storage/dhara_client.py` (the directory rename is the breaking change; the class name is preserved for backwards compat). The new file:
  - Removes the 3 Dhara imports (lines 7, 41, 42).
  - Adds: `from medium_mcp.storage.in_memory_kv import AsyncKVStore` and `from medium_mcp.utils.in_process_lock import Lock`.
  - Replaces `if self.backend == "memory":` block:
    ```python
    if self.backend == "memory":
        self._kv = AsyncKVStore()
        self._lock = Lock()
    else:
        raise ConfigurationError(
            f"unknown backend {self.backend!r}; medium-mcp v1 supports 'memory' only",
            context={"backend": self.backend},
        )
    ```
  - The `acquire_budget_lock` (line 174) and `release_budget_lock` (line 178) call sites use `self.lock.try_acquire(key, ttl_seconds=30)` and `self.lock.release(handle)` — these method signatures match the new `Lock` class.
- [ ] **Delete** `medium_mcp/dhara/kv_store.py` (its functionality is now in `medium_mcp/storage/in_memory_kv.py`).
- [ ] **Delete** `medium_mcp/dhara/__init__.py` if the directory is now empty (or keep it empty as a namespace marker; verify with `ls medium_mcp/dhara/`).
- [ ] Update `medium_mcp/dhara/__init__.py` if it exists and re-exports `DharaClient` from `medium_mcp.dhara.client` — those imports now need to point to `medium_mcp.storage.dhara_client`. Or, if the directory is deleted, update all internal callers of `from medium_mcp.dhara.client import DharaClient` to `from medium_mcp.storage.dhara_client import DharaClient`.
- [ ] Update all internal call sites identified in Phase 1 (the `rg` for `from medium_mcp.dhara\|import medium_mcp.dhara`).
- [ ] Run `pytest medium-mcp/ -v --no-cov` to confirm no test regressed. All pre-migration tests should pass with the new primitives.

#### Integration Contract ← REQUIRED
- **Triggered from**: developer / agent migrating the file path and replacing the imports.
- **Returns to / updates**: `medium_mcp/dhara/` directory is empty (or deleted); the `DharaClient` class lives at `medium_mcp/storage/dhara_client.py`; the `AsyncKVStore` class lives at `medium_mcp/storage/in_memory_kv.py`; no internal caller references the old `medium_mcp/dhara/` namespace.
- **Demonstrable by**: `rg -n 'from dhara\|import dhara' medium_mcp/ --type py` returns 0 hits; `rg -n 'from medium_mcp.dhara\|import medium_mcp.dhara' medium_mcp/ --type py` returns 0 hits (no stale internal callers); `rg 'from medium_mcp.storage.dhara_client' medium_mcp/` returns ≥1 hit; all tests green.
- **Rollback signal**: any pre-migration test now fails; or any internal caller of `medium_mcp.dhara` is missed (rg returns a hit).
- **Observability added**: none.

## Phase 4 — Documentation + commit

- [ ] Update `medium-mcp/CHANGELOG.md` under the next version: "Removed Dhara substrate imports from `medium_mcp/dhara/{client,kv_store}.py`; the `medium_mcp/dhara/` directory is dropped; the `DharaClient` class moves to `medium_mcp/storage/dhara_client.py`; the `AsyncKVStore` class moves to `medium_mcp/storage/in_memory_kv.py`; the `Lock` primitive moves to `medium_mcp/utils/in_process_lock.py` (a 30-line substrate-agnostic local copy mirroring `mahavishnu.core._lock_sentinel.Lock`'s shape)."
- [ ] Verify `pyproject.toml` deps do NOT have a new `mahavishnu` dep added (the migration is a local 30-line primitive, not a new ecosystem dep).
- [ ] Run the full test suite once more: `pytest medium-mcp/ -v --no-cov` — all green.
- [ ] Single commit on `main` (medium-mcp repo) with message: `refactor(medium-mcp): migrate off obsolete Dhara substrate (5 imports across 2 files → 0)`
- [ ] Use `git -c user.email="les@wedgwoodwebworks.com"` per `git-author-email-correct-domain.md`.
- [ ] Do NOT add `Co-Authored-By` trailer (per `feedback-no-claude-code-coauthor-attribution.md`).
- [ ] Do NOT push (per `feedback-bodai-push-is-user-controlled.md`).

#### Integration Contract ← REQUIRED
- **Triggered from**: developer / agent committing the migration.
- **Returns to / updates**: a single commit on medium-mcp `main`; the changelog entry; the `medium_mcp/dhara/` directory is removed; the 3 new modules are added.
- **Demonstrable by**: `git log --oneline -1` shows the commit message; `git show --stat HEAD` shows the 3 new files + the moved `client.py` + the deleted `kv_store.py` + the deleted `__init__.py`; `pytest` exits 0.
- **Rollback signal**: integration test in `medium-mcp/tests/integration/test_dhara_client.py` (if any) fails post-merge.
- **Observability added: none.

## Rollback signal

If Phase 3 verification fails, rollback is `git revert <commit-hash>`. The 5 Dhara imports are restored; the new primitives are unused; the `medium_mcp/dhara/` directory is restored.

## Observability added

- The local `Lock` class is intentionally minimal (no logging, no metrics). For substrate observability, the upstream `mahavishnu.core._lock_sentinel.Lock` emits `info` on `try_acquire` collisions; the medium-mcp copy does not, to avoid divergence with the original `dhara.lock.in_memory` API. If observability is needed in the future, the medium-mcp `Lock` can be extended without changing the call sites.

## Cross-references

- `feedback-substrate-compat-shim-rot.md` — the memory rule that motivates this migration
- `docs/plans/2026-09-16-dhara-mcp-retirement-plan.md` (status: complete) — the parent Dhara substrate decommissioning
- `docs/plans/2026-10-12-dhara-lock-delete.md` (in the mahavishnu repo) — the plan that will delete `dhara/dhara/lock/` AFTER this migration lands (Phase 1.5 sequencing gate)
- `mahavishnu.core._lock_sentinel.Lock` — the canonical substrate-agnostic home (not imported here per `feedback-no-bodai-mentions-in-mcp-repos`; the medium-mcp `Lock` mirrors its shape)
- `medium_mcp/dhara/client.py` (before migration) and `medium_mcp/storage/dhara_client.py` (after migration) — the file being moved
- `medium_mcp/dhara/kv_store.py` (deleted) → `medium_mcp/storage/in_memory_kv.py` (new home) — the function being moved
- `feedback-bodai-push-is-user-controlled.md` — push policy
- `feedback-no-claude-code-coauthor-attribution.md` — commit message policy
- `git-author-email-correct-domain.md` — author email policy
