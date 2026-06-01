from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, status
from structlog import getLogger

from oopsys_agent.configuration import Loggers
from oopsys_agent.domain import ErrorReport, Severity
from oopsys_agent.runtime import AppRuntime
from oopsys_agent.services.outbox import OutboxService

logger = getLogger(Loggers.api.name)

router = APIRouter(route_class=DishkaRoute, tags=["reports"])


@router.post("/reports", status_code=status.HTTP_202_ACCEPTED)
async def receive_report(
    report: ErrorReport,
    outbox: FromDishka[OutboxService],
    runtime: FromDishka[AppRuntime],
) -> dict[str, str]:
    await outbox.record_error_report(report, agent_id=runtime.agent_id)
    runtime.notify_publisher()

    log = logger.acritical if report.severity is Severity.CRITICAL else logger.aerror
    await log(
        "report received",
        service=report.service,
        environment=report.environment,
        error_type=report.exception_type,
    )
    return {"status": "accepted"}
