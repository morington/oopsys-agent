from oopsys_agent.services.docker import _format_ports


def test_format_ports_with_bindings() -> None:
    raw = {
        "80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}],
        "443/tcp": None,
    }
    assert _format_ports(raw) == ["443/tcp", "8080→80/tcp"]


def test_format_ports_with_specific_host_ip() -> None:
    raw = {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "55432"}]}
    assert _format_ports(raw) == ["127.0.0.1:55432→5432/tcp"]
