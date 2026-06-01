import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import getLogger

from oopsys_agent.configuration import Configuration, Loggers
from oopsys_agent.database.base import utc_now
from oopsys_agent.domain import AgentFault
from oopsys_agent.runtime import AppRuntime
from oopsys_agent.services.docker import DockerMonitor
from oopsys_agent.services.monitor import SystemMonitor
from oopsys_agent.services.outbox import OutboxService
from oopsys_agent.services.publisher import NatsPublisher

logger = getLogger(Loggers.publisher.name)
_BATCH = 100


class AgentScheduler:
    def __init__(
        self,
        *,
        configuration: Configuration,
        runtime: AppRuntime,
        session_factory: async_sessionmaker[AsyncSession],
        system: SystemMonitor,
        docker: DockerMonitor,
        publisher: NatsPublisher,
    ) -> None:
        self._cfg = configuration
        self._runtime = runtime
        self._session_factory = session_factory
        self._system = system
        self._docker = docker
        self._publisher = publisher
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        await self._docker.connect()
        self._runtime.docker.available = self._docker.available
        self._runtime.docker.reason = self._docker.reason
        if self._publisher.enabled:
            await self._publisher.connect()
            self._runtime.nats_connected = self._publisher.connected
        self._tasks = [
            asyncio.create_task(self._metrics_loop(), name="oopsys-metrics"),
            asyncio.create_task(self._publish_loop(), name="oopsys-publish"),
        ]
        await logger.ainfo("scheduler started", nats_enabled=self._publisher.enabled)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        await self._docker.close()
        await self._publisher.close()
        await logger.ainfo("scheduler stopped")

    def _outbox(self, session: AsyncSession) -> OutboxService:
        return OutboxService(session, subject_prefix=self._cfg.nats.subject_prefix)

    async def _guard(self, component: str, operation: str, func: Callable[[], Awaitable[None]]) -> None:
        try:
            await func()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await logger.aerror("agent fault", component=component, operation=operation, error=str(exc))
            await self._record_fault(AgentFault.from_exception(exc, component=component, operation=operation))

    async def _record_fault(self, fault: AgentFault) -> None:
        try:
            async with self._session_factory() as session:
                await self._outbox(session).record_agent_fault(fault, agent_id=self._runtime.agent_id)
            self._runtime.notify_publisher()
        except Exception as exc:
            await logger.aerror("failed to persist agent fault", error=str(exc))

    async def _metrics_loop(self) -> None:
        while True:
            await self._guard("monitor", "collect", self._collect_once)
            await asyncio.sleep(self._cfg.intervals.metrics_seconds)

    async def _collect_once(self) -> None:
        metrics = self._system.collect_server_metrics()
        async with self._session_factory() as session:
            await self._outbox(session).record_server_metrics(metrics, agent_id=self._runtime.agent_id)
        self._runtime.last_metrics_at = utc_now()

        if not self._docker.available:
            await self._docker.connect()
        self._runtime.docker.available = self._docker.available
        self._runtime.docker.reason = self._docker.reason

        if self._docker.available:
            states = await self._docker.collect()
            async with self._session_factory() as session:
                outbox = self._outbox(session)
                for state in states:
                    await outbox.record_container_state(state, agent_id=self._runtime.agent_id)
            await logger.adebug("containers collected", count=len(states))

        self._runtime.notify_publisher()

    async def _publish_loop(self) -> None:
        if not self._publisher.enabled:
            await logger.ainfo("publisher disabled; messages stay in outbox")
            return
        while True:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._runtime.wakeup.wait(), timeout=self._cfg.intervals.publish_seconds)
            self._runtime.wakeup.clear()
            await self._guard("publisher", "flush", self._flush_once)

    async def _flush_once(self) -> None:
        if not self._publisher.connected:
            await self._publisher.connect()
            self._runtime.nats_connected = self._publisher.connected
            if not self._publisher.connected:
                return

        async with self._session_factory() as session:
            outbox = self._outbox(session)
            due = await outbox.fetch_due(limit=_BATCH)
            for record in due:
                if await self._publisher.publish(record.subject, record.payload):
                    await outbox.mark_delivered(record)
                    self._runtime.last_publish_at = utc_now()
                else:
                    self._runtime.nats_connected = self._publisher.connected
                    await outbox.mark_retry(
                        record,
                        error="publish failed (no ack)",
                        next_retry_at=self._next_retry_at(record.attempts),
                    )
                    break

    def _next_retry_at(self, attempts: int):
        base = self._cfg.intervals.retry_base_seconds
        delay = min(base * (2**attempts), self._cfg.intervals.retry_max_seconds)
        return utc_now() + timedelta(seconds=delay)
