from typing import Any

import httpx

from oopsys_agent.configuration.config import AgentModel, ServerModel


class ServerDeliveryError(RuntimeError):
    pass


class ServerClient:
    def __init__(
        self, server: ServerModel, agent: AgentModel, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._server = server
        self._agent = agent
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._agent.token:
            headers["Authorization"] = f"Bearer {self._agent.token}"
        return headers

    async def send(self, envelope: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=self._server.timeout, transport=self._transport) as client:
            response = await client.post(
                self._server.ingest_url(),
                json=envelope,
                headers=self._headers(),
            )
        if response.status_code >= 400:
            raise ServerDeliveryError(f"server responded {response.status_code}")
