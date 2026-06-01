from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends

from oopsys_agent.api.security import require_token
from oopsys_agent.domain import AgentUsage
from oopsys_agent.runtime import AppRuntime
from oopsys_agent.services.monitor import SystemMonitor

router = APIRouter(route_class=DishkaRoute, tags=["usage"])


@router.post("/usage", dependencies=[Depends(require_token)])
async def usage(
    runtime: FromDishka[AppRuntime],
    monitor: FromDishka[SystemMonitor],
) -> AgentUsage:
    return monitor.collect_agent_usage(uptime_seconds=runtime.uptime_seconds())
