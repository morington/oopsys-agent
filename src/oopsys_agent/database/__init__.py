from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from oopsys_agent.database.base import Base, utc_now
from oopsys_agent.database.models import (
    AgentFaultRecord,
    AgentIdentity,
    ContainerStateRecord,
    ErrorReportRecord,
    ServerMetricRecord,
)

__all__ = [
    "AgentFaultRecord",
    "AgentIdentity",
    "Base",
    "ContainerStateRecord",
    "ErrorReportRecord",
    "ServerMetricRecord",
    "create_all",
    "utc_now",
]


async def create_all(engine: AsyncEngine, *, sqlite_path: str | None = None) -> None:
    if sqlite_path:
        Path(sqlite_path).expanduser().parent.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
