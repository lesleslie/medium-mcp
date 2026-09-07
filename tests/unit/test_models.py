from __future__ import annotations

import pytest

from medium_mcp.models.dto import (
    ArticleContent,
    ArticleMetadata,
    ArticleSummary,
    BudgetStatus,
    PublicationInfo,
    SearchArticlesPage,
    TagInfo,
    UserInfo,
)


def test_user_info_carries_all_fields() -> None:
    u = UserInfo(
        user_id="abc",
        username="les",
        fullname="Les Leslie",
        followers_count=10,
        following_count=5,
        bio="writes code",
        twitter_username="les",
    )
    assert u.user_id == "abc"
    assert u.followers_count == 10


def test_article_summary_never_has_full_text() -> None:
    """ArticleSummary has no full_text field by construction."""
    s = ArticleSummary(
        article_id="x",
        title="t",
        author_id="a",
        published_at="2026-01-01T00:00:00Z",
        reading_time=5,
        claps=10,
        url="https://medium.com/p/x",
    )
    with pytest.raises(AttributeError):
        _ = s.full_text


def test_article_metadata_has_no_full_text() -> None:
    m = ArticleMetadata(
        article_id="x",
        title="t",
        author_id="a",
        published_at="2026-01-01T00:00:00Z",
        reading_time=5,
        claps=10,
        voters=2,
        tags=["x"],
        url="https://medium.com/p/x",
        excerpt="hello",
    )
    with pytest.raises(AttributeError):
        _ = m.full_text


def test_article_content_gates_full_text() -> None:
    """ArticleContent with include_full_text=False always returns None for full_text."""
    c = ArticleContent(
        article_id="x",
        excerpt="hello",
        full_text=None,
        format="markdown",
        truncated=False,
        include_full_text=False,
    )
    assert c.full_text is None


def test_article_content_truncates_excerpt() -> None:
    long = "x" * 5000
    c = ArticleContent(
        article_id="x",
        excerpt=long,
        full_text=None,
        format="markdown",
        truncated=True,
        include_full_text=False,
    )
    assert len(c.excerpt) <= 500  # spec default excerpt_max_chars


def test_budget_status_carries_period_and_reset() -> None:
    b = BudgetStatus(
        remaining_calls=140,
        monthly_budget=150,
        period="2026-09",
        resets_at="2026-10-01T00:00:00Z",
    )
    assert b.remaining_calls == 140
    assert b.monthly_budget == 150


def test_budget_status_has_no_unimplemented_cache_stats() -> None:
    """No ``cache_hit_rate`` / ``cached_entries``: nothing computes them in v1."""
    assert "cache_hit_rate" not in BudgetStatus.model_fields
    assert "cached_entries" not in BudgetStatus.model_fields


def test_search_articles_page_carries_next_cursor() -> None:
    p = SearchArticlesPage(articles=[], next_cursor="abc")
    assert p.next_cursor == "abc"


def test_publication_info_has_search_aliases() -> None:
    p = PublicationInfo(
        publication_id="p1",
        slug="tldr",
        name="TLDR",
        description="d",
        followers_count=1000,
        url="https://medium.com/tldr",
    )
    assert p.slug == "tldr"


def test_tag_info_carries_related() -> None:
    t = TagInfo(tag="python", followers_count=100, related_tags=["django", "fastapi"])
    assert t.related_tags == ["django", "fastapi"]
