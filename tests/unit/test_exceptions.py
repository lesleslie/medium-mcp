from __future__ import annotations

import pytest

from medium_mcp.utils.exceptions import (
    BudgetExhaustedError,
    ConfigurationError,
    MediumError,
    NotFoundError,
    RateLimitedError,
    UpstreamError,
)


def test_medium_error_carries_context() -> None:
    err = MediumError("boom", context={"foo": "bar"})
    assert err.message == "boom"
    assert err.context == {"foo": "bar"}
    assert "boom" in str(err)
    assert "foo=bar" in str(err)


def test_all_subclasses_inherit_from_medium_error() -> None:
    for cls in (ConfigurationError, UpstreamError, RateLimitedError, BudgetExhaustedError, NotFoundError):
        assert issubclass(cls, MediumError), cls


def test_upstream_error_carries_status_and_body() -> None:
    err = UpstreamError("gateway timeout", status_code=504, body="<html>...</html>")
    assert err.status_code == 504
    assert err.body == "<html>...</html>"


def test_rate_limited_is_upstream_error() -> None:
    err = RateLimitedError("429 too many requests", status_code=429, body="")
    assert isinstance(err, UpstreamError)
    assert err.status_code == 429


def test_not_found_status_is_404() -> None:
    err = NotFoundError("missing", status_code=404, body="")
    assert err.status_code == 404
    assert isinstance(err, UpstreamError)


def test_budget_exhausted_carries_spec_payload() -> None:
    err = BudgetExhaustedError(
        "budget exhausted",
        requested_calls=2,
        remaining_calls=0,
        monthly_budget=150,
        period="2026-09",
        resets_at="2026-10-01T00:00:00Z",
        cached_alternatives=["user_info", "article_metadata"],
    )
    payload = err.to_payload()
    # Spec §6.2's payload does NOT carry monthly_budget; the caller learns the
    # budget from ``budget_remaining``, not from the refusal.
    assert payload == {
        "error": "budget_exhausted",
        "remaining_calls": 0,
        "requested_calls": 2,
        "period": "2026-09",
        "resets_at": "2026-10-01T00:00:00Z",
        "retryable": False,
        "cached_alternatives": ["user_info", "article_metadata"],
    }


def test_budget_exhausted_serializes_to_json() -> None:
    import json

    err = BudgetExhaustedError(
        "budget exhausted",
        requested_calls=1,
        remaining_calls=0,
        monthly_budget=150,
        period="2026-09",
        resets_at="2026-10-01T00:00:00Z",
        cached_alternatives=[],
    )
    payload = err.to_payload()
    assert json.loads(json.dumps(payload)) == payload
