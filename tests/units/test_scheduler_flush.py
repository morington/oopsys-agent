from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oopsys_agent.configuration import Configuration
from oopsys_agent.database import create_all
from oopsys_agent.domain import ErrorReport, Severity
from oopsys_agent.runtime import AppRuntime
from oopsys_agent.services.docker import DockerMonitor
from oopsys_agent.services.monitor import SystemMonitor
from oopsys_agent.services.outbox import OutboxService
from oopsys_agent.services.scheduler import AgentScheduler


class _FakePublisher:
    def __init__(self, *, ack: bool) -> None:
        self.connected = True
        self.enabled = True
        self._ack = ack
        self.published: list[str] = []

    async def connect(self) -> bool:
        self.connected = True
        return True

    async def publish(self, subject: str, payload: dict) -> bool:
        self.published.append(subject)
        return self._ack

    async def close(self) -> None:
        return None


@pytest_asyncio.fixture
async def factory(tmp_path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'sched.db'}")
    await create_all(engine)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _scheduler(factory: async_sessionmaker[AsyncSession], publisher: _FakePublisher) -> AgentScheduler:
    return AgentScheduler(
        configuration=Configuration(),
        runtime=AppRuntime(agent_id="agent-1"),
        session_factory=factory,
        system=SystemMonitor(),
        docker=DockerMonitor(),
        publisher=publisher,  # type: ignore[arg-type]
    )


async def _seed(factory: async_sessionmaker[AsyncSession]) -> None:
    async with factory() as session:
        report = ErrorReport(
            severity=Severity.ERROR,
            service="svc",
            environment="production",
            exception_type="ValueError",
            message="boom",
            traceback="tb",
        )
        await OutboxService(session, subject_prefix="oopsys").record_error_report(report, agent_id="agent-1")


async def test_flush_delivers_on_ack(factory: async_sessionmaker[AsyncSession]) -> None:
    await _seed(factory)
    publisher = _FakePublisher(ack=True)
    scheduler = _scheduler(factory, publisher)

    await scheduler._flush_once()

    assert publisher.published == ["oopsys.agents.agent-1.projects"]
    async with factory() as session:
        assert await OutboxService(session, subject_prefix="oopsys").pending_count() == 0


async def test_flush_keeps_message_without_ack(factory: async_sessionmaker[AsyncSession]) -> None:
    await _seed(factory)
    scheduler = _scheduler(factory, _FakePublisher(ack=False))

    await scheduler._flush_once()

    async with factory() as session:
        outbox = OutboxService(session, subject_prefix="oopsys")
        assert await outbox.pending_count() == 1
        due_after_retry = await outbox.fetch_due(limit=10)
        assert due_after_retry == []  # next_retry_at pushed into the future
