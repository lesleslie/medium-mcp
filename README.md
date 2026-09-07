# medium-mcp

> **Scaffold status: PyPI name reservation.** This package is a placeholder scaffold to claim
> the `medium-mcp` name on PyPI. The MCP server is not yet implemented. See
> `docs/superpowers/plans/` for the implementation plan (TBD).

MCP server for the Medium publishing platform. Provides access to:

- **Posts** — fetch, list, and search user/author articles
- **Publications** — query stories from Medium publications
- **Users** — profile data, follower counts, author metadata
- **Tags** — topic-based content discovery

## Reserve the PyPI name

```bash
cd /Users/les/Projects/medium-mcp
uv build
uv publish  # uses UV_PUBLISH_TOKEN from env
```

The package name `medium-mcp` is currently free on PyPI (verified 2026-08-31).
Publishing a placeholder 0.1.0 release locks the name.

## Architecture (planned)

Mirrors the `raindropio-mcp` pattern in this ecosystem:

- `httpx2` for the Medium REST API client
- `fastmcp` for the MCP server surface
- `oneiric` for layered config (`settings/medium-mcp.yaml`, `local.yaml`, env vars)
- `mcp-common` for bootstrap, auth, health endpoints
- `pydantic`/`pydantic-settings` for typed config models

## Status

| Phase | State |
|---|---|
| PyPI name reservation | **pending** (run `uv publish`) |
| Spec / plan | not written |
| Implementation | not started |
| Tests | not started |

## License

BSD-3-Clause.