from __future__ import annotations

from medium_mcp.dhara.keys import (
    budget_key,
    cache_key,
    coalesce_key,
    content_key,
)


def test_cache_key_is_deterministic_and_sorted() -> None:
    a = cache_key("user_info", {"user_id": "abc", "cursor": None})
    b = cache_key("user_info", {"cursor": None, "user_id": "abc"})
    assert a == b
    assert a.startswith("medium2:v1:user_info:")


def test_cache_key_different_params_differ() -> None:
    a = cache_key("user_info", {"user_id": "abc"})
    b = cache_key("user_info", {"user_id": "xyz"})
    assert a != b


def test_cache_key_normalizes_none_to_empty_string() -> None:
    a = cache_key("user_info", {"cursor": None})
    b = cache_key("user_info", {})
    # canonical serialization must produce the same hash for both
    assert a == b


def test_content_key_is_separate_prefix() -> None:
    assert content_key("abc123") == "medium2:v1:content:abc123"
    # Distinct from cache_key prefix which is ``medium2:v1:<endpoint>``
    assert not content_key("abc123").startswith("medium2:v1:user_info")


def test_budget_key_format() -> None:
    assert budget_key("2026-09") == "medium2:v1:budget:2026-09"


def test_coalesce_key_equals_cache_key() -> None:
    """Spec: coalescing attaches followers to the leader's future using the cache key."""
    params = {"foo": "bar"}
    assert coalesce_key("search_articles", params) == cache_key("search_articles", params)
