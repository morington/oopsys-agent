from unittest.mock import AsyncMock

import pytest
from faststream.exceptions import NackMessage

from oopsys_agent.configuration.config import AgentModel, NatsModel, ServerModel
from oopsys_agent.runtime import AppRuntime
from oopsys_agent.services.nats import NatsGateway
from oopsys_agent.services.server_client import ServerAuthError, ServerClient, ServerDeliveryError


def _gateway(*, runtime: AppRuntime | None = None, token: str | None = None) -> NatsGateway:
    return NatsGateway(
        NatsModel(),
        ServerClient(ServerModel(), AgentModel(token=token)),
        runtime or AppRuntime(agent_id="agent-1"),
        retry_base=0,
    )


async def test_forward_nacks_on_delivery_failure() -> None:
    gateway = _gateway()
    gateway._server_client.send = AsyncMock(side_effect=ServerDeliveryError("503"))

    with pytest.raises(NackMessage):
        await gateway._forward({"source": "projects"})

    assert gateway._runtime.server_reachable is False


async def test_forward_nacks_without_agent_token() -> None:
    gateway = _gateway()
    gateway._server_client.send = AsyncMock()

    with pytest.raises(NackMessage):
        await gateway._forward({"source": "projects"})

    gateway._server_client.send.assert_not_called()
    assert gateway._forward_no_token_logged is True


async def test_forward_nacks_on_auth_failure() -> None:
    gateway = _gateway(token="secret")
    gateway._server_client.send = AsyncMock(side_effect=ServerAuthError("401"))

    with pytest.raises(NackMessage):
        await gateway._forward({"source": "projects"})

    assert gateway._forward_auth_logged is True


async def test_forward_marks_server_reachable_on_success() -> None:
    runtime = AppRuntime(agent_id="agent-1")
    gateway = _gateway(runtime=runtime, token="secret")
    gateway._server_client.send = AsyncMock()
    runtime.server_reachable = False
    gateway._forward_unreachable_logged = True

    await gateway._forward({"source": "projects"})

    assert runtime.server_reachable is True
    assert gateway._forward_unreachable_logged is False


async def test_connect_once_fails_fast_on_unreachable_server() -> None:
    gateway = _gateway()
    gateway._config = NatsModel(servers=["nats://does-not-exist:4222"], connect_timeout=1.0)

    ok = await gateway._connect_once()

    assert ok is False
    assert gateway._runtime.queue_connected is False
    assert gateway._broker is None
