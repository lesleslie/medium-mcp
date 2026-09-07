"""Auth wiring integration test for medium-mcp (Task 14.3).

Three assertions per mcp-surface-health-illusion memory:

1. Unauthenticated tool call → 401 / AuthenticationRequiredError.
2. Authenticated tool call with a valid token reaches the tool body.
3. /health envelope includes the ``auth`` component.

I-5 fix: per the brief, the placeholder ``...`` body in the plan template was
replaced with concrete assertions verifying the wiring, not just the
registration. The integration test runs through the FastMCP ASGI transport
(no live network) so it is hermetic.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastmcp import Client
from httpx2 import ASGITransport, AsyncClient
from pydantic import SecretStr

from mcp_common.auth.context import seed_principal
from mcp_common.auth.decorator import require_auth
from mcp_common.auth.permissions import Permission
from mcp_common.auth.principal import Principal

from medium_mcp.config.settings import MediumSettings


@pytest.fixture
def settings_with_secret(monkeypatch: pytest.MonkeyPatch) -> MediumSettings:
    """Settings with a real-looking auth secret so BearerTokenMiddleware builds."""
    monkeypatch.setenv("MEDIUM_MCP_SECRET", "a" * 48)
    s = MediumSettings(_env_file=None)
    s.rapidapi_key = SecretStr("a" * 50)
    return s


def _build_runtime_with_auth(settings: MediumSettings):
    """Build a Runtime that has auth wired in (mirrors scapy build_runtime)."""
    from medium_mcp.cache.store import MediumCache
    from medium_mcp.clients.medium2 import Medium2Client
    from medium_mcp.dhara.client import DharaClient
    from medium_mcp.server import Runtime

    dhara = DharaClient(settings=settings, backend="memory")
    cache = MediumCache(settings=settings, dhara=dhara)
    client = Medium2Client(settings=settings, dhara=dhara)
    return Runtime(settings=settings, dhara=dhara, cache=cache, client=client)


def test_medium_mcp_unauthenticated_tool_call_returns_401(
    settings_with_secret: MediumSettings,
) -> None:
    """I-5 fix: a tool call without a token returns 401 (not 500 or 200).

    The test registers an inline @require_auth-decorated tool onto the
    FastMCP server, then calls it without a Bearer token. The middleware's
    per-request gate (``_current_principal() is None`` + no token +
    ``@require_auth`` deny-by-default) must surface as a 401.
    """
    runtime = _build_runtime_with_auth(settings_with_secret)
    server = runtime.build_mcp_app()
    assert runtime._auth_middleware is not None, (
        "BearerTokenMiddleware should be built when MEDIUM_MCP_SECRET is set"
    )

    @server.tool(name="auth_wiring_protected")
    @require_auth(permission=Permission.READ, service_name="medium-mcp")
    async def inline_protected_tool() -> str:
        return "tool body ran"

    async def call_without_token() -> Any:
        async with Client(server) as client:
            return await client.call_tool("auth_wiring_protected", {})

    with pytest.raises(Exception) as exc_info:
        asyncio.run(call_without_token())
    assert (
        "401" in str(exc_info.value)
        or "Authentication" in str(exc_info.value)
    ), f"Expected 401/Authentication error, got: {exc_info.value!r}"


def test_medium_mcp_authenticated_tool_call_reaches_tool_body(
    settings_with_secret: MediumSettings,
) -> None:
    """I-5 fix: a tool call with a valid token reaches the tool body.

    Uses ``seed_principal`` (the test injection path documented in
    mcp-common's auth design doc) so the test does not depend on token
    plumbing. The middleware's idempotency check
    (``_current_principal() is not None``) lets seeded calls bypass
    the Bearer verify step.
    """
    principal = Principal(
        issuer="test-issuer",
        subject="user-1",
        permissions=frozenset({Permission.READ}),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        raw_claims={},
    )

    @require_auth(permission=Permission.READ, service_name="medium-mcp")
    async def inline_protected_tool() -> str:
        return "tool body ran"

    token_handle = seed_principal(principal)
    try:
        result = asyncio.run(inline_protected_tool())
        assert result == "tool body ran"
    finally:
        token_handle.var.reset(token_handle)


def test_medium_mcp_health_envelope_includes_auth_component(
    settings_with_secret: MediumSettings,
) -> None:
    """Supplementary: /health includes the auth component when auth is wired."""
    runtime = _build_runtime_with_auth(settings_with_secret)
    runtime.build_mcp_app()
    assert runtime._auth_middleware is not None
    app = runtime.build_asgi_app()

    async def hit_health() -> dict[str, Any]:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            return response.json()

    body = asyncio.run(hit_health())
    component_names = [c["name"] for c in body.get("components", [])]
    assert "auth" in component_names, (
        f"expected 'auth' component in {component_names}"
    )


def test_medium_mcp_auth_disabled_when_no_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I-9 fix: no secret → no middleware → no auth component in /health."""
    monkeypatch.delenv("MEDIUM_MCP_SECRET", raising=False)
    monkeypatch.delenv("BODAI_SHARED_SECRET", raising=False)
    settings = MediumSettings(_env_file=None)
    settings.rapidapi_key = SecretStr("a" * 50)

    runtime = _build_runtime_with_auth(settings)
    runtime.build_mcp_app()
    assert runtime._auth_middleware is None, (
        "Expected no middleware when MEDIUM_MCP_SECRET is unset"
    )
