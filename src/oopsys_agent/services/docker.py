import contextlib
from datetime import datetime
from typing import Any

from structlog import getLogger

from oopsys_agent.configuration import Loggers
from oopsys_agent.database.base import utc_now
from oopsys_agent.domain import ContainerState

logger = getLogger(Loggers.monitor.name)


def _parse_started_at(raw: str | None) -> datetime | None:
    if not raw or raw.startswith("0001-01-01"):
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _cpu_percent(stats: dict[str, Any]) -> float | None:
    cpu = stats.get("cpu_stats", {})
    precpu = stats.get("precpu_stats", {})
    try:
        cpu_delta = cpu["cpu_usage"]["total_usage"] - precpu["cpu_usage"]["total_usage"]
        system_delta = cpu["system_cpu_usage"] - precpu.get("system_cpu_usage", 0)
    except (KeyError, TypeError):
        return None
    if system_delta <= 0 or cpu_delta < 0:
        return 0.0
    online = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage") or []) or 1
    return round((cpu_delta / system_delta) * online * 100.0, 2)


def _mem(stats: dict[str, Any]) -> tuple[int | None, float | None]:
    mem = stats.get("memory_stats", {})
    usage = mem.get("usage")
    limit = mem.get("limit")
    if usage is None:
        return None, None
    cache = mem.get("stats", {}).get("inactive_file", 0)
    real_usage = max(usage - cache, 0)
    percent = round(real_usage / limit * 100.0, 2) if limit else None
    return real_usage, percent


def _network(stats: dict[str, Any]) -> tuple[int | None, int | None]:
    networks = stats.get("networks")
    if not networks:
        return None, None
    rx = sum(n.get("rx_bytes", 0) for n in networks.values())
    tx = sum(n.get("tx_bytes", 0) for n in networks.values())
    return rx, tx


def _block_io(stats: dict[str, Any]) -> tuple[int | None, int | None]:
    entries = stats.get("blkio_stats", {}).get("io_service_bytes_recursive") or []
    read = sum(e.get("value", 0) for e in entries if e.get("op", "").lower() == "read")
    write = sum(e.get("value", 0) for e in entries if e.get("op", "").lower() == "write")
    if not entries:
        return None, None
    return read, write


class DockerMonitor:
    def __init__(self) -> None:
        self._docker: Any = None
        self.available: bool = False
        self.reason: str | None = None

    async def connect(self) -> bool:
        try:
            import aiodocker

            self._docker = aiodocker.Docker()
            await self._docker.version()
        except Exception as exc:
            self.available = False
            self.reason = str(exc)
            await self._safe_close()
            await logger.awarning("docker monitor unavailable", reason=self.reason)
            return False
        self.available = True
        self.reason = None
        return True

    async def collect(self) -> list[ContainerState]:
        if not self._docker:
            return []
        states: list[ContainerState] = []
        containers = await self._docker.containers.list(all=True)
        for container in containers:
            try:
                states.append(await self._build_state(container))
            except Exception as exc:
                await logger.adebug("skip container", container=getattr(container, "id", "?"), error=str(exc))
        return states

    async def _build_state(self, container: Any) -> ContainerState:
        info = await container.show()
        state = info.get("State", {})
        config = info.get("Config", {})
        status = state.get("Status", "unknown")

        cpu = mem_usage = mem_percent = net_rx = net_tx = blk_read = blk_write = None
        if status == "running":
            raw = await container.stats(stream=False)
            stats = raw[0] if isinstance(raw, list) and raw else raw
            if isinstance(stats, dict):
                cpu = _cpu_percent(stats)
                mem_usage, mem_percent = _mem(stats)
                net_rx, net_tx = _network(stats)
                blk_read, blk_write = _block_io(stats)

        return ContainerState(
            container_id=info.get("Id", "")[:64],
            name=info.get("Name", "").lstrip("/"),
            image=config.get("Image", ""),
            status=status,
            started_at=_parse_started_at(state.get("StartedAt")),
            restarts=info.get("RestartCount", 0),
            cpu_percent=cpu,
            mem_percent=mem_percent,
            mem_usage=mem_usage,
            net_rx=net_rx,
            net_tx=net_tx,
            blk_read=blk_read,
            blk_write=blk_write,
            labels=config.get("Labels") or {},
            captured_at=utc_now(),
        )

    async def _safe_close(self) -> None:
        if self._docker is not None:
            with contextlib.suppress(Exception):
                await self._docker.close()
            self._docker = None

    async def close(self) -> None:
        await self._safe_close()
