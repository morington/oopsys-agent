from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from oopsys_agent.database import (
    AgentFaultRecord,
    ContainerStateRecord,
    ErrorReportRecord,
    OutboxRecord,
    ServerMetricRecord,
    utc_now,
)
from oopsys_agent.domain import (
    AgentFault,
    ContainerState,
    Envelope,
    ErrorReport,
    OutboxStatus,
    ServerMetrics,
    Source,
    build_subject,
)


class OutboxService:
    def __init__(self, session: AsyncSession, *, subject_prefix: str) -> None:
        self._session = session
        self._prefix = subject_prefix

    def _enqueue(self, agent_id: str, source: Source, payload: dict) -> OutboxRecord:
        envelope = Envelope(agent_id=agent_id, source=source, payload=payload)
        record = OutboxRecord(
            subject=build_subject(self._prefix, agent_id, source),
            source=source,
            payload=envelope.model_dump(mode="json"),
        )
        self._session.add(record)
        return record

    async def record_error_report(self, report: ErrorReport, *, agent_id: str) -> None:
        self._session.add(
            ErrorReportRecord(
                severity=report.severity,
                service=report.service,
                environment=report.environment,
                exception_type=report.exception_type,
                message=report.message,
                traceback=report.traceback,
                context=report.context,
                occurred_at=report.timestamp,
            )
        )
        self._enqueue(agent_id, Source.PROJECTS, report.model_dump(mode="json"))
        await self._session.commit()

    async def record_server_metrics(self, metrics: ServerMetrics, *, agent_id: str) -> None:
        self._session.add(
            ServerMetricRecord(
                cpu_percent=metrics.cpu_percent,
                mem_percent=metrics.mem_percent,
                mem_used=metrics.mem_used,
                mem_total=metrics.mem_total,
                net_bytes_sent=metrics.net_bytes_sent,
                net_bytes_recv=metrics.net_bytes_recv,
                load_1=metrics.load_1,
                load_5=metrics.load_5,
                load_15=metrics.load_15,
                disk_percent=metrics.disk_percent,
                captured_at=metrics.captured_at,
            )
        )
        self._enqueue(agent_id, Source.SERVER, metrics.model_dump(mode="json"))
        await self._session.commit()

    async def record_container_state(self, state: ContainerState, *, agent_id: str) -> None:
        self._session.add(
            ContainerStateRecord(
                container_id=state.container_id,
                name=state.name,
                image=state.image,
                status=state.status,
                started_at=state.started_at,
                restarts=state.restarts,
                cpu_percent=state.cpu_percent,
                mem_percent=state.mem_percent,
                mem_usage=state.mem_usage,
                net_rx=state.net_rx,
                net_tx=state.net_tx,
                blk_read=state.blk_read,
                blk_write=state.blk_write,
                labels=state.labels,
                captured_at=state.captured_at,
            )
        )
        self._enqueue(agent_id, Source.DOCKER, state.model_dump(mode="json"))
        await self._session.commit()

    async def record_agent_fault(self, fault: AgentFault, *, agent_id: str) -> None:
        self._session.add(
            AgentFaultRecord(
                component=fault.component,
                operation=fault.operation,
                exception_type=fault.exception_type,
                message=fault.message,
                traceback=fault.traceback,
                severity=fault.severity,
                occurred_at=fault.occurred_at,
            )
        )
        self._enqueue(agent_id, Source.AGENT, fault.model_dump(mode="json"))
        await self._session.commit()

    async def pending_count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(OutboxRecord).where(OutboxRecord.status == OutboxStatus.PENDING)
        )
        return int(result.scalar_one())

    async def fetch_due(self, *, limit: int, now: datetime | None = None) -> list[OutboxRecord]:
        moment = now or utc_now()
        result = await self._session.execute(
            select(OutboxRecord)
            .where(
                OutboxRecord.status == OutboxStatus.PENDING,
                (OutboxRecord.next_retry_at.is_(None)) | (OutboxRecord.next_retry_at <= moment),
            )
            .order_by(OutboxRecord.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_delivered(self, record: OutboxRecord) -> None:
        record.status = OutboxStatus.DELIVERED
        record.delivered_at = utc_now()
        record.last_error = None
        await self._session.commit()

    async def mark_retry(self, record: OutboxRecord, *, error: str, next_retry_at: datetime) -> None:
        record.attempts += 1
        record.last_error = error
        record.next_retry_at = next_retry_at
        await self._session.commit()
