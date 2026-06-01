from oopsys_agent.domain import AgentFault, ErrorReport, Severity


def test_error_report_parses_minimal_payload() -> None:
    report = ErrorReport.model_validate(
        {
            "severity": "critical",
            "service": "cryptobot",
            "environment": "production",
            "exception_type": "RuntimeError",
            "message": "down",
            "traceback": "tb",
        }
    )
    assert report.severity is Severity.CRITICAL
    assert report.context == {}
    assert report.timestamp is not None


def test_agent_fault_from_exception_captures_type_and_message() -> None:
    try:
        raise ValueError("bad value")
    except ValueError as exc:
        fault = AgentFault.from_exception(exc, component="publisher", operation="flush")
    assert fault.exception_type == "ValueError"
    assert fault.message == "bad value"
    assert "ValueError" in fault.traceback
    assert fault.component == "publisher"
