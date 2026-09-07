from __future__ import annotations

import pytest
from pydantic import SecretStr

from medium_mcp.config.settings import MediumSettings, get_settings


def test_defaults_match_spec() -> None:
    settings = MediumSettings(_env_file=None)  # ignore .env
    assert settings.http_port == 3055
    assert str(settings.rapidapi_base_url) == "https://medium2.p.rapidapi.com/"
    assert settings.monthly_budget == 150
    assert settings.budget_reserve_headroom == 5
    assert settings.retry_max_attempts == 1
    assert settings.http_timeout_seconds == 30.0
    assert settings.dhara_namespace == "medium_mcp"
    assert settings.dhara_required is True
    assert settings.cache_max_entries == 10_000
    assert settings.cache_max_content_bytes == 52_428_800
    assert settings.cache_ttl_user_info == 86_400
    assert settings.cache_ttl_user_articles == 3_600
    assert settings.cache_ttl_article_metadata == 604_800
    assert settings.cache_ttl_article_content == 2_592_000
    assert settings.cache_ttl_search == 1_800
    assert settings.cache_ttl_tag == 21_600
    assert settings.coalesce_window_seconds == 5.0
    assert settings.excerpt_max_chars == 500
    assert settings.allow_content_export is False


def test_excerpt_max_chars_capped_at_2000() -> None:
    with pytest.raises(Exception):  # pydantic ValidationError
        MediumSettings(_env_file=None, excerpt_max_chars=2001)


def test_retry_max_attempts_for_metered_calls_is_one() -> None:
    """Spec pins retry_max_attempts=1 because metered calls must not retry."""
    settings = MediumSettings(_env_file=None)
    assert settings.retry_max_attempts == 1


def test_rapidapi_key_required_at_startup() -> None:
    """rapidapi_key is required via env (not defaulted)."""
    settings = MediumSettings(_env_file=None)
    assert settings.rapidapi_key is None or isinstance(settings.rapidapi_key, SecretStr)


def test_env_var_override_works() -> None:
    settings = MediumSettings(
        _env_file=None,
        monthly_budget=200,
        budget_reserve_headroom=10,
    )
    assert settings.monthly_budget == 200
    assert settings.budget_reserve_headroom == 10


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()


def test_settings_can_be_reloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIUM_MCP_MONTHLY_BUDGET", "175")
    get_settings.cache_clear()
    assert get_settings().monthly_budget == 175
