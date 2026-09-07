from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Response
from fastmcp import FastMCP
from mcp_common.auth.config import AuthConfig
from mcp_common.auth.core import JWTIdentityProvider
from mcp_common.auth.error_middleware import AuthErrorTranslationMiddleware
from mcp_common.auth.health import AuthHealth
from mcp_common.auth.identity import validate_auth_config
from mcp_common.auth.middleware import BearerTokenMiddleware
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
        self._auth_middleware: BearerTokenMiddleware | None = None
        self._last_successful_verification_at: datetime | None = None

    def _build_auth_middleware(self) -> BearerTokenMiddleware | None:
        """Construct BearerTokenMiddleware when auth is enabled.

        I-9 fix (Task 14.3): guard ``secret is None`` before
        ``.get_secret_value()``. A sibling that uses only Anthropic
        (no JWT) should not crash with AttributeError when constructing
        the providers dict.
        """
        auth_cfg = AuthConfig(
            service_name=APP_NAME,
            secret_env_var="MEDIUM_MCP_SECRET",
        )
        if not auth_cfg.enabled:
            return None

        # B6 fix: fail-loud at startup if the auth config is inconsistent
        # (empty trusted_issuers, missing default_provider, etc.) rather than
        # at the first request. Mirrors mcp-common's startup-check contract.
        validate_auth_config(auth_cfg)

        providers: dict[str, Any] = {}
        if auth_cfg.identity_providers is None or "jwt" in auth_cfg.identity_providers:
            # I-9 fix: a JWT provider requires a non-None secret. Without this
            # guard, a misconfiguration (provider declared, secret absent) crashes
            # with AttributeError on .get_secret_value() at startup.
            if auth_cfg.resolved_secret is None:
                raise RuntimeError(
                    "auth.identity_providers['jwt'] is configured but "
                    "auth.resolved_secret is None — set MEDIUM_MCP_SECRET or "
                    "BODAI_SHARED_SECRET, or remove the JWT provider."
                )
            providers["jwt"] = JWTIdentityProvider(
                name="jwt",
                secret=auth_cfg.resolved_secret,
                trusted_issuers=auth_cfg.trusted_issuers,
            )

        self._auth_middleware = BearerTokenMiddleware(
            auth_config=auth_cfg, providers=providers
        )
        return self._auth_middleware

    def _build_auth_health_provider(self):
        """I-4 fix (Task 14.3 wiring): expose middleware counters via an
        auth_health_provider callable so register_http_health_route's
        per-request is_degraded() reflects actual verifications/errors.

        Without this wiring, /health will always report
        verifications_total=0 in production — the wiring-discipline §3
        four signals (entities_count, last_updated_timestamp, errors_total,
        cycles_total) all rely on it.

        The callable is sync because ``register_http_health_route`` invokes
        ``auth_health_provider()`` and treats the result as an
        ``AuthHealth`` instance (not a coroutine). We therefore construct
        ``AuthHealth`` directly via its dataclass constructor instead of
        awaiting the async ``from_providers`` factory. Provider ``state``
        defaults to ``"healthy"`` until a verification fails.
        """
        if self._auth_middleware is None:
            return None

        def _provider() -> AuthHealth | None:
            mw = self._auth_middleware
            if mw is None:
                return None
            from mcp_common.auth.provider import ProviderHealth

            return AuthHealth(
                providers={
                    name: ProviderHealth(name=name, state="healthy")
                    for name in mw._providers
                },
                verifications_total=mw.verifications_total,
                errors_total=mw.errors_total,
                last_successful_verification_at=self._last_successful_verification_at,
            )

        return _provider

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

        # Task 14.3 wiring: BearerTokenMiddleware is constructed before
        # register_http_health_route so the auth_health_provider callable
        # captures a live reference to the middleware's counters.
        self._build_auth_middleware()
        if self._auth_middleware is not None:
            app.add_middleware(self._auth_middleware)
        # B2 fix: AuthError subclasses raised by BearerTokenMiddleware must be
        # translated to JSON-RPC -32001 with OAuth-style data. Install the
        # translator unconditionally so AuthErrors surfaced by future
        # middleware (or by @require_auth) hit the same shape end-to-end.
        app.add_middleware(AuthErrorTranslationMiddleware())
        register_http_health_route(
            app,
            service_name=APP_NAME,
            version=__version__,
            extra_components=as_components(),
            auth_health_provider=self._build_auth_health_provider(),
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
