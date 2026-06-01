import asyncio
import contextlib
from collections.abc import Awaitable, Callable

from oopsys_agent.configuration import Configuration, Loggers
from oopsys_agent.database.base import utc_now
from oopsys_agent.domain import AgentFault, ContainerSnapshot
from oopsys_agent.runtime import AppRuntime
from oopsys_agent.services.docker import DockerMonitor
from oopsys_agent.services.events import EventService
from oopsys_agent.services.monitor import SystemMonitor
from oopsys_agent.services.nats import NatsGateway
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import getLogger

logger = getLogger(Loggers.monitor.name)


class AgentScheduler:
    """Background monitoring: collect host metrics and container states on an interval."""

    def __init__(
        self,
        *,
        configuration: Configuration,
        runtime: AppRuntime,
        session_factory: async_sessionmaker[AsyncSession],
        system: SystemMonitor,
        docker: DockerMonitor,
        gateway: NatsGateway,
    ) -> None:
        self._cfg = configuration
        self._runtime = runtime
        self._session_factory = session_factory
        self._system = system
        self._docker = docker
        self._gateway = gateway
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        await self._docker.connect()
        self._runtime.docker.available = self._docker.available
        self._runtime.docker.reason = self._docker.reason
        self._tasks = [asyncio.create_task(self._metrics_loop(), name="oopsys-metrics")]
        await logger.ainfo("scheduler started")

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        await self._docker.close()
        await logger.ainfo("scheduler stopped")

    def _events(self, session: AsyncSession) -> EventService:
        return EventService(
            session, self._gateway, subject_prefix=self._cfg.nats.subject_prefix
        )

    async def _guard(
        self, component: str, operation: str, func: Callable[[], Awaitable[None]]
    ) -> None:
        try:
            await func()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await logger.aerror(
                "agent fault", component=component, operation=operation, error=str(exc)
            )
            await self._record_fault(
                AgentFault.from_exception(exc, component=component, operation=operation)
            )

    async def _record_fault(self, fault: AgentFault) -> None:
        try:
            async with self._session_factory() as session:
                await self._events(session).record_agent_fault(
                    fault, agent_id=self._runtime.agent_id
                )
        except Exception as exc:
            await logger.aerror("failed to record agent fault", error=str(exc))

    async def _metrics_loop(self) -> None:
        while True:
            await self._guard("monitor", "collect", self._collect_once)
            await asyncio.sleep(self._cfg.intervals.metrics_seconds)

    async def _collect_once(self) -> None:
        metrics = self._system.collect_server_metrics()
        async with self._session_factory() as session:
            await self._events(session).record_server_metrics(
                metrics, agent_id=self._runtime.agent_id
            )
        self._runtime.last_metrics_at = utc_now()

        if not self._docker.available:
            await self._docker.connect()
        self._runtime.docker.available = self._docker.available
        self._runtime.docker.reason = self._docker.reason

        if self._docker.available:
            states = await self._docker.collect()
            snapshot = ContainerSnapshot(captured_at=utc_now(), containers=states)
            async with self._session_factory() as session:
                await self._events(session).record_container_snapshot(
                    snapshot, agent_id=self._runtime.agent_id
                )
            await logger.adebug("containers collected", count=len(states))
