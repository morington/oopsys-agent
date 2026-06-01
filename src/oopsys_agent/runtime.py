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
    queue_connected: bool = False
    server_reachable: bool = False
    last_metrics_at: datetime | None = None
    last_forwarded_at: datetime | None = None

    def uptime_seconds(self) -> float:
        return (utc_now() - self.started_at).total_seconds()
