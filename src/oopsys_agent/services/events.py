from oopsys_agent.database import (
    AgentFaultRecord,
    ContainerStateRecord,
    ErrorReportRecord,
    ServerMetricRecord,
)
from oopsys_agent.domain import (
    AgentFault,
    ContainerSnapshot,
    ContainerState,
    Envelope,
    ErrorReport,
    ServerMetrics,
    Source,
    build_subject,
)
from oopsys_agent.services.nats import NatsGateway
from sqlalchemy.ext.asyncio import AsyncSession


class EventService:
    """Persist an event to local history (SQLite) and enqueue it for delivery."""

    def __init__(
        self, session: AsyncSession, gateway: NatsGateway, *, subject_prefix: str
    ) -> None:
        self._session = session
        self._gateway = gateway
        self._prefix = subject_prefix

    async def _enqueue(self, agent_id: str, source: Source, payload: dict) -> None:
        envelope = Envelope(agent_id=agent_id, source=source, payload=payload)
        subject = build_subject(self._prefix, agent_id, source)
        await self._gateway.publish(subject, envelope.model_dump(mode="json"))

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
        await self._session.commit()
        await self._enqueue(agent_id, Source.PROJECTS, report.model_dump(mode="json"))

    async def record_server_metrics(
        self, metrics: ServerMetrics, *, agent_id: str
    ) -> None:
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
        await self._session.commit()
        await self._enqueue(agent_id, Source.SERVER, metrics.model_dump(mode="json"))

    async def record_container_snapshot(
        self, snapshot: ContainerSnapshot, *, agent_id: str
    ) -> None:
        for state in snapshot.containers:
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
        await self._session.commit()
        await self._enqueue(agent_id, Source.DOCKER, snapshot.model_dump(mode="json"))

    async def record_container_state(
        self, state: ContainerState, *, agent_id: str
    ) -> None:
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
        await self._session.commit()
        await self._enqueue(agent_id, Source.DOCKER, state.model_dump(mode="json"))

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
        await self._session.commit()
        await self._enqueue(agent_id, Source.AGENT, fault.model_dump(mode="json"))
