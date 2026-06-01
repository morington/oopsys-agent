from oopsys_agent.services.docker import (
    _block_io,
    _cpu_percent,
    _mem,
    _network,
    _parse_started_at,
)

_STATS = {
    "cpu_stats": {
        "cpu_usage": {"total_usage": 200, "percpu_usage": [1, 1]},
        "system_cpu_usage": 2000,
        "online_cpus": 2,
    },
    "precpu_stats": {"cpu_usage": {"total_usage": 100}, "system_cpu_usage": 1000},
    "memory_stats": {"usage": 1048576, "limit": 10485760, "stats": {"inactive_file": 48576}},
    "networks": {"eth0": {"rx_bytes": 500, "tx_bytes": 700}},
    "blkio_stats": {"io_service_bytes_recursive": [{"op": "Read", "value": 100}, {"op": "Write", "value": 200}]},
}


def test_cpu_percent() -> None:
    assert _cpu_percent(_STATS) == 20.0


def test_cpu_percent_handles_missing_keys() -> None:
    assert _cpu_percent({}) is None


def test_mem_subtracts_inactive_file() -> None:
    usage, percent = _mem(_STATS)
    assert usage == 1000000
    assert percent == 9.54


def test_network_sums_interfaces() -> None:
    assert _network(_STATS) == (500, 700)


def test_block_io_splits_read_write() -> None:
    assert _block_io(_STATS) == (100, 200)


def test_parse_started_at_zero_is_none() -> None:
    assert _parse_started_at("0001-01-01T00:00:00Z") is None


def test_parse_started_at_parses_nanoseconds() -> None:
    parsed = _parse_started_at("2024-05-01T10:00:00.123456789Z")
    assert parsed is not None
    assert parsed.year == 2024
