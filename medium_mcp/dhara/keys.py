from __future__ import annotations

import hashlib
import json
from typing import Any

NAMESPACE_PREFIX = "medium2:v1"


def _canonical_params(params: dict[str, Any]) -> bytes:
    """Canonically encode params for hashing.

    Rules: drop ``None`` keys (so ``{"cursor": None}`` and ``{}`` hash the same),
    keys sorted, JSON dump with compact separators.
    """
    normalized = {k: v for k, v in params.items() if v is not None}
    return json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()


def _hash_params(params: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_params(params)).hexdigest()


def cache_key(endpoint: str, params: dict[str, Any]) -> str:
    """Cache key: namespace + endpoint + sha256 of canonical params."""
    return f"{NAMESPACE_PREFIX}:{endpoint}:{_hash_params(params)}"


def content_key(article_id: str) -> str:
    """Separate key prefix for full-text content per spec §6.2 content policy."""
    return f"{NAMESPACE_PREFIX}:content:{article_id}"


def budget_key(period: str) -> str:
    """Counter key. No TTL — must not evict across the month boundary."""
    return f"{NAMESPACE_PREFIX}:budget:{period}"


def coalesce_key(endpoint: str, params: dict[str, Any]) -> str:
    """Coalescing shares the cache key (spec §6.2)."""
    return cache_key(endpoint, params)
