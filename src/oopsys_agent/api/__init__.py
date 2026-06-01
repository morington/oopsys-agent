from fastapi import FastAPI

from oopsys_agent.api.health import public_router
from oopsys_agent.api.health import router as health_router
from oopsys_agent.api.reports import router as reports_router
from oopsys_agent.api.usage import router as usage_router


def include_routers(app: FastAPI) -> None:
    app.include_router(public_router)
    app.include_router(health_router)
    app.include_router(usage_router)
    app.include_router(reports_router)


__all__ = ["include_routers"]
