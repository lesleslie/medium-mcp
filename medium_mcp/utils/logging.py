from __future__ import annotations

from oneiric.core.logging import LoggingConfig
from oneiric.core.logging import configure_logging as _oneiric_configure

_configured = False


def configure_logging(level: str | None = None) -> None:
    """Configure oneiric logging once per process.

    Called from ``build_runtime()`` — the single startup entry point — not at
    module import time and not per-module. The ``_configured`` latch makes a
    second call a no-op so a test that builds two runtimes does not end up with
    duplicated handlers and doubled log lines.

    ``level`` defaults to ``MediumSettings.log_level``; it is passed in rather
    than read here so this module does not import settings and create a cycle.
    """
    global _configured
    if _configured:
        return
    from medium_mcp.config.settings import get_settings

    _oneiric_configure(LoggingConfig(level=(level or get_settings().log_level).upper()))
    _configured = True
