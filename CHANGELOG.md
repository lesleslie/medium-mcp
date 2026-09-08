# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-09-07

### Added

- Call validate_auth_config at startup
- medium-mcp: 13 tools + budget_remaining + content-policy gate
- medium-mcp: API key validation at startup
- medium-mcp: Cache store with TTL-by-endpoint, content prefix, coalesce
- medium-mcp: Dhara client + key scheme for cache, content, budget, coalesce
- medium-mcp: Initialize git repo, switch to flat layout, packaging test
- medium-mcp: MediumSettings with all §13.3 keys and defaults
- medium-mcp: Server.py with baseline tools, health routes, profile dispatch
- medium-mcp: Typed DTO models for all 13 tools + content policy
- medium-mcp: Typed exception hierarchy with structured BudgetExhaustedError
- medium-mcp: Typed httpx2 client with atomic budget reservation + dhara gate
- Register AuthErrorTranslationMiddleware for JSON-RPC -32001
- Wire BearerTokenMiddleware + AuthHealth into medium-mcp server

### Fixed

- medium-mcp: Mount FastMCP under FastAPI for /readyz + /health

### Documentation

- medium-mcp: Correct README to name medium2 RapidAPI + content policy

### Testing

- medium-mcp: Per-tool e2e tests asserting non-empty results
- medium-mcp: Phase 0b upstream proof test (auto-skips without MEDIUM_MCP_RAPIDAPI_KEY)

### Internal

- deps: Pin mcp-common to local dev path for auth surface
- medium-mcp: Ratchet coverage to 85, decision record
- medium-mcp: Ruff gate clean — drop TCH/SIM108, rename CoalesceTimeoutError
