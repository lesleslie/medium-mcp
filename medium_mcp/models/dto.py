from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from medium_mcp.config.settings import MediumSettings


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class UserInfo(_Base):
    user_id: str = Field(validation_alias="id")
    username: str | None = None
    fullname: str | None = None
    followers_count: int = 0
    following_count: int = 0
    bio: str | None = None
    twitter_username: str | None = None


class ArticleSummary(_Base):
    """Never carries full_text — that lives only in ArticleContent."""

    article_id: str = Field(validation_alias="id")
    title: str
    author_id: str = Field(validation_alias="author")
    published_at: str  # ISO-8601 from upstream
    reading_time: int = 0
    claps: int = 0
    url: str


class ArticleMetadata(_Base):
    article_id: str = Field(validation_alias="id")
    title: str
    subtitle: str | None = None
    author_id: str = Field(validation_alias="author")
    published_at: str
    reading_time: int = 0
    claps: int = 0
    voters: int = 0
    tags: list[str] = Field(default_factory=list)
    url: str
    excerpt: str = ""


class ArticleContent(_Base):
    article_id: str
    excerpt: str
    full_text: str | None
    format: Literal["markdown", "html", "text"]
    truncated: bool
    include_full_text: bool  # reflects the caller's request

    @field_validator("excerpt")
    @classmethod
    def _truncate_excerpt(cls, v: str) -> str:
        cap = MediumSettings(_env_file=None).excerpt_max_chars
        if len(v) > cap:
            return v[:cap]
        return v


class _ArticlesPage(_Base):
    articles: list[ArticleSummary]
    next_cursor: str | None = None


class _UsersPage(_Base):
    users: list[UserInfo]
    next_cursor: str | None = None


class _PublicationsPage(_Base):
    publications: list[PublicationInfo]
    next_cursor: str | None = None


class UserArticlesPage(_ArticlesPage):
    pass


class ArticleResponsesPage(_ArticlesPage):
    pass


class PublicationArticlesPage(_ArticlesPage):
    pass


class TagLatestPage(_ArticlesPage):
    pass


class SearchArticlesPage(_ArticlesPage):
    pass


class SearchUsersPage(_UsersPage):
    pass


class SearchPublicationsPage(_PublicationsPage):
    pass


class PublicationInfo(_Base):
    publication_id: str = Field(validation_alias="id")
    slug: str | None = None
    name: str
    description: str | None = None
    followers_count: int = 0
    url: str | None = None


class TagInfo(_Base):
    tag: str
    followers_count: int = 0
    related_tags: list[str] = Field(default_factory=list)


class BudgetStatus(_Base):
    """What ``budget_remaining`` returns.

    Deliberately has no ``cache_hit_rate`` / ``cached_entries``: nothing in v1
    computes them, and shipping zero-valued fields would read as a feature that
    does not exist. Add them only alongside a real implementation.
    """

    remaining_calls: int
    monthly_budget: int
    period: str  # YYYY-MM
    resets_at: str  # ISO-8601


# Resolve the forward reference so Pydantic can resolve PublicationInfo in _PublicationsPage.
_PublicationsPage.model_rebuild()
