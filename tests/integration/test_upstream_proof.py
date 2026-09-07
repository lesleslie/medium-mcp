"""Phase 0b — one recorded live upstream call.

HUMAN PREREQUISITE: this test blocks until ``MEDIUM_MCP_RAPIDAPI_KEY`` is
exported in the developer's shell. Per spec §11 item 1 the prerequisite is
never waived; the test auto-skips when the key is missing and a record in
``tests/fixtures/medium2_user_live.json`` is the only artifact that ever
documents the live shape.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx2
import pytest

from medium_mcp.auth.key import validate_rapidapi_key
from medium_mcp.clients.medium2 import Medium2Client
from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.mark.requires_network
@pytest.mark.requires_auth
@pytest.mark.skipif(
    not os.environ.get("MEDIUM_MCP_RAPIDAPI_KEY"),
    reason="requires MEDIUM_MCP_RAPIDAPI_KEY in env",
)
async def test_user_info_returns_real_medium_user() -> None:
    settings = MediumSettings(_env_file=None)
    settings.rapidapi_key = type(settings.rapidapi_key)(
        validate_rapidapi_key(settings.rapidapi_key)
    )
    dhara = DharaClient(settings=settings, backend="memory")
    await dhara.startup()
    try:
        client = Medium2Client(settings=settings, dhara=dhara)
        # Reach upstream directly without the budget guard (proof only).
        base = str(settings.rapidapi_base_url).rstrip("/")
        headers = {
            "X-RapidAPI-Key": settings.rapidapi_key.get_secret_value(),
            "X-RapidAPI-Host": "medium2.p.rapidapi.com",
        }
        async with httpx2.AsyncClient(timeout=30) as http:
            response = await http.get(f"{base}/user/id/1a2b", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert "id" in body, body
        # Record the fixture for offline replay in subsequent runs.
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "medium2_user_live.json").write_text(json.dumps(body, indent=2))
    finally:
        await dhara.shutdown()
