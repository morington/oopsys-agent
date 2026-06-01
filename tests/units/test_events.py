from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from oopsys_agent.database import ErrorReportRecord
from oopsys_agent.domain import ErrorReport, Severity
from oopsys_agent.services.events import EventService


class _FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def publish(self, subject: str, payload: dict) -> bool:
        self.calls.append((subject, payload))
        return True


def _report() -> ErrorReport:
    return ErrorReport(
        severity=Severity.ERROR,
        service="cryptobot",
        environment="production",
        exception_type="ValueError",
        message="boom",
        traceback="tb",
    )


async def test_record_error_report_persists_history(session: AsyncSession) -> None:
    gateway = _FakeGateway()
    await EventService(session, gateway, subject_prefix="oopsys").record_error_report(_report(), agent_id="agent-1")  # type: ignore[arg-type]

    count = await session.execute(select(func.count()).select_from(ErrorReportRecord))
    assert int(count.scalar_one()) == 1


async def test_record_error_report_enqueues_with_subject(session: AsyncSession) -> None:
    gateway = _FakeGateway()
    await EventService(session, gateway, subject_prefix="oopsys").record_error_report(_report(), agent_id="agent-1")  # type: ignore[arg-type]

    assert len(gateway.calls) == 1
    subject, payload = gateway.calls[0]
    assert subject == "oopsys.agents.agent-1.projects"
    assert payload["source"] == "projects"
    assert payload["agent_id"] == "agent-1"
