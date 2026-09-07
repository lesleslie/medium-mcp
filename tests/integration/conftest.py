from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from pydantic import SecretStr

from medium_mcp.cache.store import MediumCache
from medium_mcp.clients.medium2 import Medium2Client
from medium_mcp.config.settings import MediumSettings
from medium_mcp.dhara.client import DharaClient


@pytest.fixture
def settings() -> MediumSettings:
    s = MediumSettings(_env_file=None)
    s.rapidapi_key = SecretStr("a" * 50)
    return s


@pytest.fixture
async def dhara(settings: MediumSettings) -> DharaClient:
    client = DharaClient(settings=settings, backend="memory")
    await client.startup()
    yield client
    await client.shutdown()


@pytest.fixture
def stub_json() -> Callable[[int, dict[str, Any]], httpx2.MockTransport]:
    def _factory(status: int, body: dict[str, Any]) -> httpx2.MockTransport:
        def handler(_request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(status_code=status, json=body)

        return httpx2.MockTransport(handler)

    return _factory


@pytest.fixture
def stub_bytes() -> Callable[[int, bytes], httpx2.MockTransport]:
    def _factory(status: int, body: bytes) -> httpx2.MockTransport:
        def handler(_request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(status_code=status, content=body)

        return httpx2.MockTransport(handler)

    return _factory


@pytest.fixture
def cache(settings: MediumSettings, dhara: DharaClient) -> MediumCache:
    return MediumCache(settings=settings, dhara=dhara)


@pytest.fixture
def make_client(
    settings: MediumSettings, dhara: DharaClient
) -> Callable[[httpx2.MockTransport], tuple[Medium2Client, MediumCache]]:
    def _factory(transport: httpx2.MockTransport) -> tuple[Medium2Client, MediumCache]:
        client = Medium2Client(settings=settings, dhara=dhara, transport=transport)
        cache = MediumCache(settings=settings, dhara=dhara)
        return client, cache

    return _factory
