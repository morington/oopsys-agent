import contextlib
from typing import Any

from faststream.nats import JStream, NatsBroker
from structlog import getLogger

from oopsys_agent.configuration import Loggers
from oopsys_agent.configuration.config import NatsModel

logger = getLogger(Loggers.publisher.name)


class NatsPublisher:
    def __init__(self, config: NatsModel) -> None:
        self._config = config
        self._broker: NatsBroker | None = None
        self.connected: bool = False

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def _build_broker(self) -> NatsBroker:
        broker = NatsBroker(self._config.servers, connect_timeout=int(self._config.connect_timeout))
        stream = JStream(
            name=self._config.stream,
            subjects=[f"{self._config.subject_prefix}.agents.*.>"],
            declare=True,
        )
        broker.publisher(f"{self._config.subject_prefix}.agents._declare", stream=stream)
        return broker

    async def connect(self) -> bool:
        if not self._config.enabled:
            return False
        if self._broker is not None and self.connected:
            return True

        await self._safe_close()
        broker = self._build_broker()
        try:
            await broker.connect()
            await broker.start()
        except Exception as exc:
            self.connected = False
            with contextlib.suppress(Exception):
                await broker.stop()
            await logger.awarning("nats connect failed", reason=str(exc))
            return False

        self._broker = broker
        self.connected = True
        await logger.ainfo("nats connected", servers=self._config.servers, stream=self._config.stream)
        return True

    async def publish(self, subject: str, payload: dict[str, Any]) -> bool:
        if self._broker is None:
            return False
        try:
            ack = await self._broker.publish(
                payload,
                subject,
                stream=self._config.stream,
                timeout=self._config.publish_timeout,
            )
        except Exception as exc:
            self.connected = False
            await logger.adebug("nats publish failed", subject=subject, reason=str(exc))
            return False
        return ack is not None

    async def _safe_close(self) -> None:
        if self._broker is not None:
            with contextlib.suppress(Exception):
                await self._broker.stop()
        self._broker = None

    async def close(self) -> None:
        await self._safe_close()
        self.connected = False
