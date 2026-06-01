from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ServerMetrics(BaseModel):
    cpu_percent: float
    mem_percent: float
    mem_used: int
    mem_total: int
    net_bytes_sent: int
    net_bytes_recv: int
    load_1: float
    load_5: float
    load_15: float
    disk_percent: float | None = None
    captured_at: datetime


class ContainerState(BaseModel):
    container_id: str
    name: str
    image: str
    status: str
    started_at: datetime | None = None
    restarts: int = 0
    cpu_percent: float | None = None
    mem_percent: float | None = None
    mem_usage: int | None = None
    net_rx: int | None = None
    net_tx: int | None = None
    blk_read: int | None = None
    blk_write: int | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    ports: list[str] = Field(default_factory=list)
    health: str | None = None
    captured_at: datetime


class ContainerSnapshot(BaseModel):
    """All containers on the host at a point in time."""

    captured_at: datetime
    containers: list[ContainerState] = Field(default_factory=list)


class AgentUsage(BaseModel):
    cpu_percent: float
    rss: int
    vms: int
    num_threads: int
    num_fds: int | None = None
    uptime_seconds: float
    host_cpu_percent: float | None = None
    host_mem_percent: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
