import os

import psutil

from oopsys_agent.database.base import utc_now
from oopsys_agent.domain import AgentUsage, ServerMetrics

_CPU_SAMPLE_INTERVAL = 0.1


class SystemMonitor:
    def __init__(self) -> None:
        self._process = psutil.Process()

    def collect_server_metrics(self) -> ServerMetrics:
        mem = psutil.virtual_memory()
        net = psutil.net_io_counters()
        try:
            load_1, load_5, load_15 = os.getloadavg()
        except (OSError, AttributeError):
            load_1 = load_5 = load_15 = 0.0
        disk_percent: float | None
        try:
            disk_percent = psutil.disk_usage("/").percent
        except OSError:
            disk_percent = None

        return ServerMetrics(
            cpu_percent=psutil.cpu_percent(interval=_CPU_SAMPLE_INTERVAL),
            mem_percent=mem.percent,
            mem_used=mem.used,
            mem_total=mem.total,
            net_bytes_sent=net.bytes_sent,
            net_bytes_recv=net.bytes_recv,
            load_1=load_1,
            load_5=load_5,
            load_15=load_15,
            disk_percent=disk_percent,
            captured_at=utc_now(),
        )

    def collect_agent_usage(self, *, uptime_seconds: float) -> AgentUsage:
        with self._process.oneshot():
            mem = self._process.memory_info()
            cpu = self._process.cpu_percent(interval=_CPU_SAMPLE_INTERVAL)
            num_threads = self._process.num_threads()
            try:
                num_fds = self._process.num_fds()
            except (psutil.Error, AttributeError):
                num_fds = None

        return AgentUsage(
            cpu_percent=cpu,
            rss=mem.rss,
            vms=mem.vms,
            num_threads=num_threads,
            num_fds=num_fds,
            uptime_seconds=uptime_seconds,
            host_cpu_percent=psutil.cpu_percent(interval=None),
            host_mem_percent=psutil.virtual_memory().percent,
        )
