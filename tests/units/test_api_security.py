from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from dishka.integrations.fastapi import FastapiProvider
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from oopsys_agent.dependency_injection import build_container
from oopsys_agent.main import create_app
from oopsys_agent.runtime import AppRuntime
from oopsys_agent.services import TokenService


@pytest_asyncio.fixture
async def client_and_token(monkeypatch, tmp_path) -> AsyncIterator[tuple[httpx.AsyncClient, str]]:
    monkeypatch.setenv("SQLITE__PATH", str(tmp_path / "agent.db"))

    runtime = AppRuntime(agent_id="test-agent")
    container = build_container(FastapiProvider(), context={AppRuntime: runtime})
    app = create_app(container)

    factory = await container.get(async_sessionmaker[AsyncSession])
    async with factory() as session:
        created = await TokenService(session).create_token()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        yield client, created.token
    await container.close()


async def test_ping_is_public(client_and_token) -> None:
    client, _ = client_and_token
    response = await client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


async def test_health_requires_token(client_and_token) -> None:
    client, _ = client_and_token
    response = await client.post("/health")
    assert response.status_code == 401


async def test_health_accepts_valid_token(client_and_token) -> None:
    client, token = client_and_token
    response = await client.post("/health", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == "test-agent"
    assert body["status"] == "alive"


async def test_health_rejects_invalid_token(client_and_token) -> None:
    client, _ = client_and_token
    response = await client.post("/health", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401
