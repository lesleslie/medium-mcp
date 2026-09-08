from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastmcp import FastMCP
from mcp_common.tools.dispatch import ALL_TOOLS
from mcp_common.tools.profiles import ToolProfile

from medium_mcp.cache.store import MediumCache
from medium_mcp.clients.medium2 import Medium2Client
from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient

MEDIUM_MANDATORY_GROUPS: set[str] = {"health_tools"}

# Which groups each profile exposes, keyed by ``ToolProfile``. The values of
# ``MEDIUM_MCP_TOOL_PROFILE`` are mapped through ``ToolProfile``; the dispatcher
# reads the env var and looks the group list up in this table.
PROFILE_REGISTRATIONS: dict[
    ToolProfile,
    list[str | Callable[[FastMCP], Awaitable[None] | None]] | type[ALL_TOOLS],
] = {
    ToolProfile.FULL: ALL_TOOLS,
    ToolProfile.STANDARD: [
        "health_tools",
        "budget_tools",
        "user_tools",
        "article_tools",
        "publication_tools",
        "tag_tools",
    ],
    ToolProfile.MINIMAL: ["health_tools", "budget_tools"],
}


@dataclass
class ClientBundle:
    settings: MediumSettings
    dhara: DharaClient
    cache: MediumCache
    client: Medium2Client


def _register_health_tools(_server: FastMCP) -> None:
    """Health group — present at every profile.

    The four Bodai baseline tools (discover_tools, get_liveness, get_readiness,
    health_check_all) are registered globally by ``bootstrap_baseline_tools``
    in ``server.py``, so this group is intentionally a no-op. It exists so the
    profile dispatch table carries the group key and ``mandatory_groups``
    resolves to a real entry.
    """


def _build_registration_map(
    bundle: ClientBundle,
) -> dict[str, Callable[[FastMCP], Awaitable[None] | None]]:
    """Map group keys to their registration callables.

    The dispatcher invokes each callable against the FastMCP ``app``. Returning
    callables (not lists) is what the dispatch contract expects — a list of
    tool names here triggers the ``'list' object is not callable`` error seen
    in the dual-track drift pattern.
    """
    return {
        "health_tools": _register_health_tools,
        "user_tools": lambda srv: _register_user_tools(srv, bundle),
        "article_tools": lambda srv: _register_article_tools(srv, bundle),
        "publication_tools": lambda srv: _register_publication_tools(srv, bundle),
        "tag_tools": lambda srv: _register_tag_tools(srv, bundle),
        "search_tools": lambda srv: _register_search_tools(srv, bundle),
        "budget_tools": lambda srv: _register_budget_tools(srv, bundle),
    }


def _register_user_tools(app: FastMCP, bundle: ClientBundle) -> None:
    from medium_mcp.tools import users

    @app.tool(name=users.user_info.__name__)
    async def _user_info(user_id: str | None = None, username: str | None = None) -> dict:
        result = await users.user_info(
            settings=bundle.settings,
            dhara=bundle.dhara,
            cache=bundle.cache,
            client=bundle.client,
            user_id=user_id,
            username=username,
        )
        return result.model_dump()

    @app.tool(name=users.user_articles.__name__)
    async def _user_articles(user_id: str, cursor: str | None = None) -> dict:
        result = await users.user_articles(
            settings=bundle.settings,
            dhara=bundle.dhara,
            cache=bundle.cache,
            client=bundle.client,
            user_id=user_id,
            cursor=cursor,
        )
        return result.model_dump()


def _register_article_tools(app: FastMCP, bundle: ClientBundle) -> None:
    from medium_mcp.tools import articles

    @app.tool(name=articles.article_metadata.__name__)
    async def _article_metadata(article_id: str) -> dict:
        result = await articles.article_metadata(
            settings=bundle.settings,
            dhara=bundle.dhara,
            cache=bundle.cache,
            client=bundle.client,
            article_id=article_id,
        )
        return result.model_dump()

    @app.tool(name=articles.article_content.__name__)
    async def _article_content(
        article_id: str, include_full_text: bool = False, format: str = "markdown"
    ) -> dict:
        result = await articles.article_content(
            settings=bundle.settings,
            dhara=bundle.dhara,
            cache=bundle.cache,
            client=bundle.client,
            article_id=article_id,
            include_full_text=include_full_text,
            format=format,  # ty: ignore[invalid-argument-type]
        )
        return result.model_dump()

    @app.tool(name=articles.article_responses.__name__)
    async def _article_responses(article_id: str, cursor: str | None = None) -> dict:
        result = await articles.article_responses(
            settings=bundle.settings,
            dhara=bundle.dhara,
            cache=bundle.cache,
            client=bundle.client,
            article_id=article_id,
            cursor=cursor,
        )
        return result.model_dump()


def _register_publication_tools(app: FastMCP, bundle: ClientBundle) -> None:
    from medium_mcp.tools import publications

    @app.tool(name=publications.publication_info.__name__)
    async def _publication_info(publication_id: str | None = None, slug: str | None = None) -> dict:
        result = await publications.publication_info(
            settings=bundle.settings,
            dhara=bundle.dhara,
            cache=bundle.cache,
            client=bundle.client,
            publication_id=publication_id,
            slug=slug,
        )
        return result.model_dump()

    @app.tool(name=publications.publication_articles.__name__)
    async def _publication_articles(publication_id: str, cursor: str | None = None) -> dict:
        result = await publications.publication_articles(
            settings=bundle.settings,
            dhara=bundle.dhara,
            cache=bundle.cache,
            client=bundle.client,
            publication_id=publication_id,
            cursor=cursor,
        )
        return result.model_dump()


def _register_tag_tools(app: FastMCP, bundle: ClientBundle) -> None:
    from medium_mcp.tools import tags

    @app.tool(name=tags.tag_info.__name__)
    async def _tag_info(tag: str) -> dict:
        result = await tags.tag_info(
            settings=bundle.settings,
            dhara=bundle.dhara,
            cache=bundle.cache,
            client=bundle.client,
            tag=tag,
        )
        return result.model_dump()

    @app.tool(name=tags.tag_latest.__name__)
    async def _tag_latest(tag: str, cursor: str | None = None) -> dict:
        result = await tags.tag_latest(
            settings=bundle.settings,
            dhara=bundle.dhara,
            cache=bundle.cache,
            client=bundle.client,
            tag=tag,
            cursor=cursor,
        )
        return result.model_dump()


def _register_search_tools(app: FastMCP, bundle: ClientBundle) -> None:
    from medium_mcp.tools import search

    @app.tool(name=search.search_articles.__name__)
    async def _search_articles(query: str, cursor: str | None = None) -> dict:
        result = await search.search_articles(
            settings=bundle.settings,
            dhara=bundle.dhara,
            cache=bundle.cache,
            client=bundle.client,
            query=query,
            cursor=cursor,
        )
        return result.model_dump()

    @app.tool(name=search.search_users.__name__)
    async def _search_users(query: str, cursor: str | None = None) -> dict:
        result = await search.search_users(
            settings=bundle.settings,
            dhara=bundle.dhara,
            cache=bundle.cache,
            client=bundle.client,
            query=query,
            cursor=cursor,
        )
        return result.model_dump()

    @app.tool(name=search.search_publications.__name__)
    async def _search_publications(query: str, cursor: str | None = None) -> dict:
        result = await search.search_publications(
            settings=bundle.settings,
            dhara=bundle.dhara,
            cache=bundle.cache,
            client=bundle.client,
            query=query,
            cursor=cursor,
        )
        return result.model_dump()


def _register_budget_tools(app: FastMCP, bundle: ClientBundle) -> None:
    from medium_mcp.tools import budget

    @app.tool(name=budget.budget_remaining.__name__)
    async def _budget_remaining() -> dict:
        result = await budget.budget_remaining(
            settings=bundle.settings,
            dhara=bundle.dhara,
            cache=bundle.cache,
            client=bundle.client,
        )
        return result.model_dump()


def register_all_tool_groups(app: FastMCP, bundle: ClientBundle) -> None:
    """Register every domain tool group against the FastMCP ``app``.

    Called by the dispatcher's ``register_all_fn`` when ``PROFILE_REGISTRATIONS[FULL]``
    is the ``ALL_TOOLS`` sentinel. The map itself is passed separately as
    ``registration_map`` so this function returns ``None`` to match the
    dispatcher's ``Callable[[FastMCP], Awaitable[None] | None] | None`` contract.
    """
    registration_map = _build_registration_map(bundle)
    for fn in registration_map.values():
        fn(app)
