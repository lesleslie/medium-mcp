from __future__ import annotations

from pydantic import SecretStr

from medium_mcp.config.settings import MediumSettings
from medium_mcp.server import build_runtime, get_app

# The four tools mcp_common's bootstrap installs on every Bodai MCP server.
# Mirrors archive-org-mcp. If this set shrinks, the wiring-discipline health
# aggregation loses its probes.
EXPECTED_BASELINE = {
    "discover_tools",
    "get_liveness",
    "get_readiness",
    "health_check_all",
}


def settings() -> MediumSettings:
    s = MediumSettings(_env_file=None)
    s.rapidapi_key = SecretStr("a" * 50)
    return s


def test_app_is_fastmcp_instance() -> None:
    from fastmcp import FastMCP

    # Lazy accessor — avoids `validate_rapidapi_key` running at import time.
    assert isinstance(get_app(), FastMCP)


def test_build_runtime_with_in_memory_dhara() -> None:
    runtime = build_runtime(settings=settings(), dhara_backend="memory")
    assert runtime.dhara is not None
    assert runtime.cache is not None
    assert runtime.client is not None


async def test_baseline_tools_are_registered() -> None:
    """bootstrap_baseline_tools must run before any domain group is registered."""
    runtime = build_runtime(settings=settings(), dhara_backend="memory")
    mcp_app = runtime.build_mcp_app()
    names = {t.name for t in await mcp_app.list_tools()}
    missing = EXPECTED_BASELINE - names
    assert not missing, f"baseline tools missing: {sorted(missing)}"


async def test_domain_tools_registered_alongside_baseline() -> None:
    """The full profile exposes the 13 domain tools plus the baseline four."""
    runtime = build_runtime(settings=settings(), dhara_backend="memory")
    mcp_app = runtime.build_mcp_app()
    names = {t.name for t in await mcp_app.list_tools()}
    assert "budget_remaining" in names
    assert "article_content" in names
    assert names >= EXPECTED_BASELINE
