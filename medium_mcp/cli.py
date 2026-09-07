from __future__ import annotations

import asyncio

from medium_mcp.config.settings import get_settings
from medium_mcp.server import build_runtime


def main() -> None:
    settings = get_settings()
    runtime = build_runtime(settings=settings, dhara_backend="memory")
    mcp_app = runtime.build_mcp_app()
    asyncio.run(runtime.dhara.startup())
    try:
        mcp_app.run(transport="streamable-http", port=settings.http_port or 3055)
    finally:
        asyncio.run(runtime.dhara.shutdown())


if __name__ == "__main__":
    main()
