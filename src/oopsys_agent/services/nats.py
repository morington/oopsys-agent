import asyncio
import contextlib
from typing import Any

from faststream import AckPolicy
from faststream.exceptions import NackMessage
from faststream.nats import JStream, NatsBroker
from nats.js.api import ConsumerConfig
from structlog import getLogger

from oopsys_agent.configuration.config import NatsModel
from oopsys_agent.configuration.loggers import Loggers
from oopsys_agent.database.base import utc_now
from oopsys_agent.runtime import AppRuntime
from oopsys_agent.services.server_client import ServerAuthError, ServerClient, ServerDeliveryError

logger = getLogger(Loggers.publisher.name)


class NatsGateway:
    """
    Local durable queue (NATS JetStream) plus the forwarder worker.

    Collected events are published to the queue. A JetStream consumer reads the
    queue and delivers each message to the server over HTTP; if the server is
    down the handler raises and the message is nacked, so nothing is lost.
    """

    def __init__(
        self, config: NatsModel, server_client: ServerClient, runtime: AppRuntime, *, retry_base: float
    ) -> None:
        self._config = config
        self._server_client = server_client
        self._runtime = runtime
        self._retry_base = retry_base
        self._broker: NatsBroker | None = None
        self._retry_task: asyncio.Task | None = None
        self._forward_no_token_logged = False
        self._forward_auth_logged = False
        self._forward_unreachable_logged = False
        self._connect_failed_logged = False

    def _stream(self) -> JStream:
        return JStream(
            name=self._config.stream,
            subjects=[f"{self._config.subject_prefix}.agents.*.>"],
            declare=True,
        )

    def _build_broker(self) -> NatsBroker:
        broker = NatsBroker(
            self._config.servers,
            connect_timeout=int(self._config.connect_timeout),
            max_reconnect_attempts=1,
            logger=None,
        )
        stream = self._stream()
        broker.publisher(f"{self._config.subject_prefix}.agents._declare", stream=stream)
        broker.subscriber(
            f"{self._config.subject_prefix}.agents.*.>",
            stream=stream,
            durable=self._config.durable,
            pull_sub=True,
            ack_policy=AckPolicy.NACK_ON_ERROR,
            config=ConsumerConfig(ack_wait=self._config.ack_wait, max_deliver=-1),
        )(self._forward)
        return broker

    async def _forward(self, body: dict[str, Any]) -> None:
        if not self._server_client.delivery_enabled:
            self._runtime.server_reachable = False
            if not self._forward_no_token_logged:
                await logger.awarning(
                    "forwarding disabled: set AGENT__TOKEN in .env after `oopsys-agent token create`",
                )
                self._forward_no_token_logged = True
            raise NackMessage() from None

        try:
            await self._server_client.send(body)
        except ServerAuthError as exc:
            self._runtime.server_reachable = False
            if not self._forward_auth_logged:
                await logger.awarning(
                    "token rejected by server; bind the same token in Agents UI",
                    reason=str(exc),
                )
                self._forward_auth_logged = True
            raise NackMessage() from None
        except (ServerDeliveryError, Exception) as exc:
            was_reachable = self._runtime.server_reachable
            self._runtime.server_reachable = False
            if was_reachable or not self._forward_unreachable_logged:
                await logger.awarning(
                    "server unreachable; messages stay in queue and will retry",
                    reason=str(exc),
                )
                self._forward_unreachable_logged = True
            raise NackMessage() from None
        if not self._runtime.server_reachable:
            await logger.ainfo("server reachable again; forwarding resumed")
        self._forward_no_token_logged = False
        self._forward_auth_logged = False
        self._forward_unreachable_logged = False
        self._runtime.server_reachable = True
        self._runtime.last_forwarded_at = utc_now()

    async def _connect_once(self) -> bool:
        await self._safe_close()
        broker = self._build_broker()
        try:
            await broker.connect()
            await broker.start()
        except Exception as exc:
            self._runtime.queue_connected = False
            with contextlib.suppress(Exception):
                await broker.stop()
            if not self._connect_failed_logged:
                hint = (
                    "check NATS__SERVERS matches the docker-compose service name "
                    "(expected nats://oopsys-nats:4222)"
                )
                await logger.awarning(
                    "nats connect failed",
                    servers=self._config.servers,
                    reason=str(exc),
                    hint=hint,
                )
                self._connect_failed_logged = True
            return False
        self._broker = broker
        self._runtime.queue_connected = True
        self._connect_failed_logged = False
        await logger.ainfo("nats queue ready", servers=self._config.servers, stream=self._config.stream)
        return True

    async def _retry_loop(self) -> None:
        while True:
            if await self._connect_once():
                return
            await asyncio.sleep(self._retry_base)

    async def start(self) -> bool:
        connected = await self._connect_once()
        if connected:
            return True
        self._retry_task = asyncio.create_task(self._retry_loop(), name="oopsys-nats-retry")
        return False

    async def publish(self, subject: str, payload: dict[str, Any]) -> bool:
        if self._broker is None:
            return False
        try:
            await self._broker.publish(
                payload,
                subject,
                stream=self._config.stream,
                timeout=self._config.publish_timeout,
            )
        except Exception as exc:
            self._runtime.queue_connected = False
            await logger.aerror("enqueue failed", subject=subject, reason=str(exc))
            return False
        return True

    async def _safe_close(self) -> None:
        if self._broker is not None:
            with contextlib.suppress(Exception):
                await self._broker.stop()
        self._broker = None

    async def close(self) -> None:
        if self._retry_task is not None:
            self._retry_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._retry_task
            self._retry_task = None
        await self._safe_close()
        self._runtime.queue_connected = False
