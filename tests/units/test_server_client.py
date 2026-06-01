import httpx
import pytest

from oopsys_agent.configuration.config import AgentModel, ServerModel
from oopsys_agent.services.server_client import ServerAuthError, ServerClient, ServerDeliveryError


def _client(handler, *, token: str | None = None) -> ServerClient:
    return ServerClient(
        ServerModel(url="http://server:8000", ingest_path="/agents/ingest"),
        AgentModel(token=token),
        transport=httpx.MockTransport(handler),
    )


async def test_send_posts_envelope_to_ingest_url() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(202)

    await _client(handler, token="secret").send({"source": "projects"})

    assert seen["url"] == "http://server:8000/agents/ingest"
    assert seen["auth"] == "Bearer secret"


async def test_send_raises_on_server_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with pytest.raises(ServerDeliveryError):
        await _client(handler).send({"source": "server"})


async def test_send_raises_auth_error_on_unauthorized() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    with pytest.raises(ServerAuthError):
        await _client(handler, token="secret").send({"source": "projects"})


async def test_delivery_disabled_without_token() -> None:
    assert _client(lambda _: httpx.Response(202)).delivery_enabled is False
    assert _client(lambda _: httpx.Response(202), token="x").delivery_enabled is True
