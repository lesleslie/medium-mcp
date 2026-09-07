from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import FastAPI, Response
from fastmcp import FastMCP
from mcp_common.baseline_tools import seed_liveness_context
from mcp_common.bootstrap import bootstrap_baseline_tools
from mcp_common.health import register_http_health_route
from mcp_common.tools.dispatch import _apply_tool_profile

from medium_mcp import __version__
from medium_mcp.auth.key import validate_rapidapi_key
from medium_mcp.cache.store import MediumCache
from medium_mcp.clients.medium2 import Medium2Client
from medium_mcp.config.settings import MediumSettings, get_settings
from medium_mcp.dhara.client import DharaClient
from medium_mcp.feeds import FEEDS, as_components, required_feeds_healthy
from medium_mcp.tools.profiles import (
    MEDIUM_MANDATORY_GROUPS,
    PROFILE_REGISTRATIONS,
    ClientBundle,
    _build_registration_map,
    register_all_tool_groups,
)
from medium_mcp.utils.logging import configure_logging

APP_NAME = "medium-mcp"


def _run_async_safely(coro: Any) -> Any:
    """Run an awaitable from a sync context, bridging asyncio.run or a worker thread."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


def build_runtime(
    *,
    settings: MediumSettings | None = None,
    dhara_backend: str = "memory",
) -> Runtime:
    s = settings or get_settings()
    # Configure logging exactly once, at the single startup entry point.
    # Never at module import time and never per-module: a second call would
    # re-attach handlers and duplicate every line.
    configure_logging(level=s.log_level)
    # Validate the API key at startup. We require it even when no metered call
    # has been made yet, because tools cannot run without it.
    validate_rapidapi_key(s.rapidapi_key)
    dhara = DharaClient(settings=s, backend=dhara_backend)
    cache = MediumCache(settings=s, dhara=dhara)
    client = Medium2Client(settings=s, dhara=dhara)
    return Runtime(settings=s, dhara=dhara, cache=cache, client=client)


class Runtime:
    def __init__(
        self,
        *,
        settings: MediumSettings,
        dhara: DharaClient,
        cache: MediumCache,
        client: Medium2Client,
    ) -> None:
        self.settings = settings
        self.dhara = dhara
        self.cache = cache
        self.client = client
        self.asgi_app: FastAPI | None = None
        self._mcp_app: FastMCP | None = None

    def build_mcp_app(self) -> FastMCP:
        if self._mcp_app is not None:
            return self._mcp_app
        bundle = ClientBundle(
            settings=self.settings,
            dhara=self.dhara,
            cache=self.cache,
            client=self.client,
        )
        app = FastMCP(name=APP_NAME, version=__version__)

        # ORDERING IS LOAD-BEARING. Baseline tools and the liveness context must
        # be installed BEFORE any domain group is registered, and the domain
        # groups must be registered *through* apply_tool_profile. @app.tool is a
        # one-way door: registering the 13 tools first and then pruning the
        # registration map would leave the map claiming a group is hidden while
        # the decorator has already exposed it — the dual-track drift.
        seed_liveness_context(service_name=APP_NAME, version=__version__)
        bootstrap_baseline_tools(app)
        register_http_health_route(
            app,
            service_name=APP_NAME,
            version=__version__,
            extra_components=as_components(),
        )

        # Profile dispatch. Sync ``apply_tool_profile`` raises when called from
        # within a running event loop (the case under pytest-asyncio), so we use
        # the async helper directly when one is available and the sync wrapper
        # otherwise. Both produce the same registration result.
        try:
            asyncio.get_running_loop()
            _async_dispatch_available = True
        except RuntimeError:
            _async_dispatch_available = False

        if _async_dispatch_available:
            _run_async_safely(
                _apply_tool_profile(
                    app,
                    profile_env_var="MEDIUM_MCP_TOOL_PROFILE",
                    registrations=PROFILE_REGISTRATIONS,
                    registration_map=_build_registration_map(bundle),
                    register_all_fn=lambda srv: register_all_tool_groups(srv, bundle),
                    mandatory_groups=MEDIUM_MANDATORY_GROUPS,
                    essential_tool_names={"health_check_all"},
                )
            )
        else:
            from mcp_common.tools.dispatch import apply_tool_profile

            apply_tool_profile(
                app,
                profile_env_var="MEDIUM_MCP_TOOL_PROFILE",
                registrations=PROFILE_REGISTRATIONS,
                registration_map=_build_registration_map(bundle),
                register_all_fn=lambda srv: register_all_tool_groups(srv, bundle),
                mandatory_groups=MEDIUM_MANDATORY_GROUPS,
                essential_tool_names={"health_check_all"},
            )

        self._mcp_app = app
        return app

    def build_asgi_app(self) -> FastAPI:
        if self.asgi_app is not None:
            return self.asgi_app
        mcp_app = self.build_mcp_app()
        upstream = mcp_app.http_app()  # type: ignore[no-any-return]

        # Mount the FastMCP ASGI app under a FastAPI wrapper so we can add
        # /readyz alongside /health. The FastMCP http_app() returns a
        # StarletteWithLifespan that doesn't accept custom_route.
        wrapper = FastAPI(title="medium-mcp")

        @wrapper.get("/readyz")
        async def _readyz() -> Response:
            await self.dhara.startup()
            reachable = await self.dhara.probe()
            if not reachable:
                FEEDS["medium2"].record_cycle(error="dhara unreachable")
                return Response(
                    content='{"status":"degraded","reason":"dhara unreachable"}',
                    status_code=503,
                    media_type="application/json",
                )
            if not required_feeds_healthy():
                return Response(
                    content='{"status":"degraded","reason":"required feed not healthy"}',
                    status_code=503,
                    media_type="application/json",
                )
            return Response(
                content='{"status":"ok"}',
                status_code=200,
                media_type="application/json",
            )

        wrapper.mount("/", upstream)
        self.asgi_app = wrapper
        return wrapper


_default_runtime: Runtime | None = None


def _get_runtime() -> Runtime:
    global _default_runtime
    if _default_runtime is None:
        _default_runtime = build_runtime()
    return _default_runtime


def get_app() -> FastMCP:
    """Lazy accessor — avoids `validate_rapidapi_key` running at import time.

    Importing `medium_mcp.server` no longer requires `MEDIUM_MCP_RAPIDAPI_KEY`
    to be present in the environment. Callers that need the app (the CLI, the
    FastMCP runner, integration tests) call `get_app()` explicitly.
    """
    return _get_runtime().build_mcp_app()


if __name__ == "__main__":
    get_app().run()
