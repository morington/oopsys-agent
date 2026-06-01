import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from oopsys_agent.database.base import utc_now


@dataclass
class DockerStatus:
    available: bool = False
    reason: str | None = None


@dataclass
class AppRuntime:
    agent_id: str = ""
    started_at: datetime = field(default_factory=utc_now)
    docker: DockerStatus = field(default_factory=DockerStatus)
    nats_connected: bool = False
    last_metrics_at: datetime | None = None
    last_publish_at: datetime | None = None
    wakeup: asyncio.Event = field(default_factory=asyncio.Event)

    def uptime_seconds(self) -> float:
        return (utc_now() - self.started_at).total_seconds()

    def notify_publisher(self) -> None:
        self.wakeup.set()
