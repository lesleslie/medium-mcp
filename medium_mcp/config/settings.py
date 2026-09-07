from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class MediumSettings(BaseSettings):
    """Configuration for medium-mcp. Spec source: §13.3."""

    model_config = SettingsConfigDict(
        env_prefix="MEDIUM_MCP_",
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Network
    rapidapi_base_url: HttpUrl = "https://medium2.p.rapidapi.com"
    rapidapi_key: SecretStr | None = None
    http_port: int | None = 3055
    http_timeout_seconds: float = 30.0

    # Budget
    monthly_budget: int = 150
    budget_reserve_headroom: int = 5
    # Spec rule: metered calls must not retry. Single attempt only.
    retry_max_attempts: int = Field(default=1, ge=0, le=1)

    # Cache
    dhara_namespace: str = "medium_mcp"
    dhara_required: bool = True
    cache_max_entries: int = 10_000
    cache_max_content_bytes: int = 52_428_800
    cache_ttl_user_info: int = 86_400
    cache_ttl_user_articles: int = 3_600
    cache_ttl_article_metadata: int = 604_800
    cache_ttl_article_content: int = 2_592_000
    cache_ttl_search: int = 1_800
    cache_ttl_tag: int = 21_600
    coalesce_window_seconds: float = 5.0

    # Content policy
    excerpt_max_chars: int = Field(default=500, gt=0, le=2000)
    allow_content_export: bool = False

    # Profile / logging
    tool_profile: str = "full"
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> MediumSettings:
    """Cached singleton. Callers can call `.cache_clear()` after env mutation."""
    return MediumSettings()
