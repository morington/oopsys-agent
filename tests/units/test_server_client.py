import httpx
import pytest

from oopsys_agent.configuration.config import AgentModel, ServerModel
from oopsys_agent.services.server_client import ServerClient, ServerDeliveryError


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
