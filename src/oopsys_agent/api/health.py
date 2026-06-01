from typing import Any

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends

from oopsys_agent.api.security import require_token
from oopsys_agent.runtime import AppRuntime
from oopsys_agent.services.outbox import OutboxService
from oopsys_agent.version import get_version

public_router = APIRouter(tags=["health"])
router = APIRouter(route_class=DishkaRoute, tags=["health"])


@public_router.get("/ping")
async def ping() -> dict[str, str]:
    return {"status": "alive"}


@router.post("/health", dependencies=[Depends(require_token)])
async def health(
    runtime: FromDishka[AppRuntime],
    outbox: FromDishka[OutboxService],
) -> dict[str, Any]:
    try:
        pending = await outbox.pending_count()
        sqlite_state: dict[str, Any] = {"ok": True, "outbox_pending": pending}
    except Exception as exc:
        sqlite_state = {"ok": False, "error": str(exc)}

    docker_state: dict[str, Any] = {"available": runtime.docker.available}
    if not runtime.docker.available:
        docker_state["status"] = "docker monitor unavailable"
        docker_state["reason"] = runtime.docker.reason

    return {
        "status": "alive",
        "agent_id": runtime.agent_id,
        "version": get_version(),
        "uptime_seconds": runtime.uptime_seconds(),
        "sqlite": sqlite_state,
        "nats": {"connected": runtime.nats_connected},
        "docker": docker_state,
        "last_metrics_at": runtime.last_metrics_at.isoformat() if runtime.last_metrics_at else None,
    }
