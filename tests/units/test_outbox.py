from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from oopsys_agent.database.base import utc_now
from oopsys_agent.domain import ErrorReport, Severity, Source
from oopsys_agent.services.outbox import OutboxService


def _report() -> ErrorReport:
    return ErrorReport(
        severity=Severity.ERROR,
        service="cryptobot",
        environment="production",
        exception_type="ValueError",
        message="boom",
        traceback="tb",
    )


async def test_record_error_report_enqueues(session: AsyncSession) -> None:
    outbox = OutboxService(session, subject_prefix="oopsys")
    await outbox.record_error_report(_report(), agent_id="agent-1")
    assert await outbox.pending_count() == 1


async def test_enqueued_subject_matches_source(session: AsyncSession) -> None:
    outbox = OutboxService(session, subject_prefix="oopsys")
    await outbox.record_error_report(_report(), agent_id="agent-1")
    due = await outbox.fetch_due(limit=10)
    assert due[0].subject == "oopsys.agents.agent-1.projects"
    assert due[0].source == Source.PROJECTS


async def test_mark_delivered_drops_from_pending(session: AsyncSession) -> None:
    outbox = OutboxService(session, subject_prefix="oopsys")
    await outbox.record_error_report(_report(), agent_id="agent-1")
    (record,) = await outbox.fetch_due(limit=10)
    await outbox.mark_delivered(record)
    assert await outbox.pending_count() == 0


async def test_mark_retry_sets_future_next_retry(session: AsyncSession) -> None:
    outbox = OutboxService(session, subject_prefix="oopsys")
    await outbox.record_error_report(_report(), agent_id="agent-1")
    (record,) = await outbox.fetch_due(limit=10)
    await outbox.mark_retry(record, error="no ack", next_retry_at=utc_now() + timedelta(hours=1))
    assert record.attempts == 1
    assert await outbox.fetch_due(limit=10) == []
