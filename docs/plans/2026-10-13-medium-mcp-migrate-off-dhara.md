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
# If this plan's `git push` happens after the dhara delete, the import
# in `medium_mcp/dhara/client.py:7` will break at module load. The
# recommended order is: this plan lands → dhara delete lands.
topic: medium-mcp-migrate-off-dhara
title: "Migrate medium-mcp off obsolete Dhara substrate (Phase 1.5 gate for dhara-lock-delete)"
---

# Migrate `medium-mcp` off the obsolete Dhara substrate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the 3 Dhara substrate imports from `medium-mcp` (`from dhara.lock.in_memory import InMemoryDharaLock`, `from dhara.core.connection import AsyncConnection`, `from dhara.storage.memory import AsyncMemoryStorage`) and replace them with substrate-agnostic in-process primitives — a 30-line lock shim and a 20-line KV-store shim, both living in `medium_mcp/utils/` and `medium_mcp/storage/`. After this lands, `rg -n 'from dhara.lock\|import dhara.lock' /Users/les/Projects/medium-mcp/ --type py` returns 0 hits and the `2026-10-12-dhara-lock-delete.md` plan can safely delete `dhara/dhara/lock/`. Per `feedback-substrate-compat-shim-rot.md`: the Dhara substrate was decommissioned (see `docs/plans/2026-09-16-dhara-mcp-retirement-plan.md` status: complete); the lock primitive was re-homed to `mahavishnu.core._lock_sentinel.Lock` for substrate-agnostic coordination, but `medium-mcp` is a `*-mcp` repo (per `feedback-no-bodai-mentions-in-mcp-repos`) and cannot take a new `mahavishnu` runtime dep without violating the rule. The right primitive for `medium-mcp` is its own in-process lock.

**Architecture:** The migration is 3 files added + 1 file modified. The new `medium_mcp/utils/in_process_lock.py` is a 30-line substrate-agnostic sentinel (mirrors `mahavishnu/core/_lock_sentinel.Lock`'s shape — `try_acquire(key, ttl_seconds=...)` returning `None` on contention). The new `medium_mcp/storage/in_memory_kv.py` is a 20-line `AsyncKVStore` shim wrapping a `dict[str, bytes]` in an `asyncio.Lock` (replaces `dhara.storage.memory.AsyncMemoryStorage` + `dhara.core.connection.AsyncConnection` which together provided the same in-memory store the medium-mcp `DharaClient` already wraps via its own `medium_mcp/dhara/kv_store.py`). The `medium_mcp/dhara/client.py` is updated to import from the new modules; the `DharaClient` class name is preserved (it's the local API surface; the "dhara" in the path is local naming, not a substrate import).

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

## Phase 1 — Inventory the Dhara footprint

- [ ] Run `rg -n 'from dhara\|import dhara' /Users/les/Projects/medium-mcp/medium_mcp/ --type py` and capture the full hit list. Expected: 3 hits — `medium_mcp/dhara/client.py:7` (`InMemoryDharaLock`), `medium_mcp/dhara/client.py:41` (`AsyncConnection`), `medium_mcp/dhara/client.py:42` (`AsyncMemoryStorage`).
- [ ] Confirm `medium_mcp/dhara/kv_store.py` is **medium-mcp's own** module (verify by reading the file — it should NOT import from `dhara.*` itself; it should be a local implementation).
- [ ] Run `pytest medium-mcp/ -v --no-cov` to establish the pre-migration baseline (all tests green).

#### Integration Contract ← REQUIRED
- **Triggered from**: developer / agent running the inventory before adding the new modules.
- **Returns to / updates**: nothing persisted; a captured baseline of the 3 Dhara call sites and the pre-migration test pass.
- **Demonstrable by**: the rg output matches the expected 3 hits; `pytest` exits 0.
- **Rollback signal**: not applicable — Phase 1 is read-only.
- **Observability added**: none.

## Phase 2 — Add the substrate-agnostic primitives

- [ ] Create `medium_mcp/utils/in_process_lock.py` with `from __future__ import annotations` as the first non-comment line. Define a `Lock` class:
  ```python
  class Lock:
      """Substrate-agnostic in-process lock for medium-mcp (mirrors
      mahavishnu.core._lock_sentinel.Lock's shape; see
      feedback-substrate-compat-shim-rot.md).
      """
      def __init__(self) -> None:
          self._items: dict[str, object] = {}
      def try_acquire(self, key: str, *, owner_token: str | None = None, ttl_seconds: int | None = None, permanent: bool = False) -> object | None:
          # ... mirror the sentinel's try_acquire logic ...
      def get(self, key: str) -> object | None: ...
      def release(self, handle: object) -> bool: ...
  ```
  The exact API matches `dhara.lock.in_memory.InMemoryDharaLock` (the call sites use `try_acquire(key, ttl_seconds=N)` and `release(handle)` — see `medium_mcp/dhara/client.py:176` and `:179`).
- [ ] Add unit tests in `medium-mcp/tests/utils/test_in_process_lock.py`:
  - `test_try_acquire_returns_handle_on_first_call` — `try_acquire("k", ttl_seconds=30)` returns a handle.
  - `test_try_acquire_returns_none_on_contention` — second call with same key returns `None`.
  - `test_release_clears_the_lock` — `release(handle)` then `try_acquire` again succeeds.
- [ ] Create `medium_mcp/storage/in_memory_kv.py` with the same shape. Define an `AsyncKVStore` class with `put_async(key, value: bytes, *, ttl: int | None = None)`, `get_async(key) -> {"value": bytes | None, ...}`. Backed by `dict[str, bytes]` + `asyncio.Lock`. TTL is a no-op for the in-process backend (the `medium-mcp` config disables TTL in its current usage; verify before assuming).
- [ ] Add unit tests in `medium-mcp/tests/storage/test_in_memory_kv.py`:
  - `test_put_then_get_round_trip`
  - `test_get_missing_key_returns_empty_dict`
  - `test_concurrent_puts_are_serialized` (asyncio.gather test).

#### Integration Contract ← REQUIRED
- **Triggered from**: developer / agent reading the original Dhara API surface and writing the shims.
- **Returns to / updates**: 2 new modules in `medium_mcp/utils/` and `medium_mcp/storage/`, with passing unit tests.
- **Demonstrable by**: `pytest medium-mcp/tests/utils/test_in_process_lock.py medium-mcp/tests/storage/test_in_memory_kv.py -v --no-cov` shows all tests green.
- **Rollback signal**: a unit test in the new modules fails for ≥1 commit after merge.
- **Observability added**: none.

## Phase 3 — Migrate `DharaClient` to the new primitives

- [ ] Edit `medium_mcp/dhara/client.py`:
  - Remove the 3 Dhara imports (lines 7, 41, 42).
  - Add: `from medium_mcp.storage.in_memory_kv import AsyncKVStore` and `from medium_mcp.utils.in_process_lock import Lock`.
  - In `DharaClient.__init__` (line 25), change `self._lock: InMemoryDharaLock | None = None` to `self._lock: Lock | None = None`.
  - In `startup` (line 37), replace the `if self.backend == "memory":` block:
    ```python
    if self.backend == "memory":
        self._kv = AsyncKVStore()
        self._lock = Lock()
    else:
        raise ConfigurationError(...)
    ```
  - The rest of the class (`acquire_budget_lock` at :174, `release_budget_lock` at :178) uses `self.lock.try_acquire(key, ttl_seconds=30)` and `self.lock.release(handle)` — these method signatures match the new `Lock` class.
- [ ] Run `pytest medium-mcp/ -v --no-cov` to confirm no test regressed. All pre-migration tests should pass with the new primitives.

#### Integration Contract ← REQUIRED
- **Triggered from**: developer / agent replacing the imports in `DharaClient`.
- **Returns to / updates**: `medium_mcp/dhara/client.py` no longer imports from `dhara.*`; the `DharaClient` API is unchanged.
- **Demonstrable by**: `rg -n 'from dhara\|import dhara' medium_mcp/ --type py` returns 0 hits (only docstring mentions of "dhara" in the path/comment); all tests green.
- **Rollback signal**: any pre-migration test now fails.
- **Observability added**: none.

## Phase 4 — Documentation + commit

- [ ] Update `medium-mcp/CHANGELOG.md` under the next version: "Removed Dhara substrate imports from `medium_mcp/dhara/client.py`; replaced with in-process substrate-agnostic primitives (`medium_mcp.utils.in_process_lock.Lock` + `medium_mcp.storage.in_memory_kv.AsyncKVStore`). The `DharaClient` class is preserved as the local API surface; the `medium_mcp/dhara/` path is retained as local naming."
- [ ] Verify `pyproject.toml` deps do NOT have a new `mahavishnu` dep added (the migration is a local 30-line primitive, not a new ecosystem dep).
- [ ] Run the full test suite once more: `pytest medium-mcp/ -v --no-cov` — all green.
- [ ] Single commit on `main` (medium-mcp repo) with message: `refactor(medium-mcp): migrate off obsolete Dhara substrate (substrate-agnostic in-process primitives)`
- [ ] Use `git -c user.email="les@wedgwoodwebworks.com"` per `git-author-email-correct-domain.md`.
- [ ] Do NOT add `Co-Authored-By` trailer (per `feedback-no-claude-code-coauthor-attribution.md`).
- [ ] Do NOT push (per `feedback-bodai-push-is-user-controlled.md`).

#### Integration Contract ← REQUIRED
- **Triggered from**: developer / agent committing the migration.
- **Returns to / updates**: a single commit on medium-mcp `main`; the changelog entry.
- **Demonstrable by**: `git log --oneline -1` shows the commit message; `git show --stat HEAD` shows the 2 new files + the modified `client.py`; `pytest` exits 0.
- **Rollback signal**: integration test in `medium-mcp/tests/integration/test_dhara_client.py` (if any) fails post-merge.
- **Observability added: none.

## Rollback signal

If Phase 3 verification fails, rollback is `git revert <commit-hash>`. The 3 Dhara imports are restored in `client.py`; the new primitives are unused.

## Observability added

- The local `Lock` class is intentionally minimal (no logging, no metrics). For substrate observability, the upstream `mahavishnu.core._lock_sentinel.Lock` emits `info` on `try_acquire` collisions; the medium-mcp copy does not, to avoid divergence with the original `dhara.lock.in_memory` API. If observability is needed in the future, the medium-mcp `Lock` can be extended without changing the call sites.

## Cross-references

- `feedback-substrate-compat-shim-rot.md` — the memory rule that motivates this migration
- `docs/plans/2026-09-16-dhara-mcp-retirement-plan.md` (status: complete) — the parent Dhara substrate decommissioning
- `docs/plans/2026-10-12-dhara-lock-delete.md` (in the mahavishnu repo) — the plan that will delete `dhara/dhara/lock/` AFTER this migration lands (Phase 1.5 sequencing gate)
- `mahavishnu.core._lock_sentinel.Lock` — the canonical substrate-agnostic home (not imported here per `feedback-no-bodai-mentions-in-mcp-repos`; the medium-mcp `Lock` mirrors its shape)
- `medium_mcp/dhara/client.py` — the file being modified
- `feedback-bodai-push-is-user-controlled.md` — push policy
- `feedback-no-claude-code-coauthor-attribution.md` — commit message policy
- `git-author-email-correct-domain.md` — author email policy
