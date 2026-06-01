from oopsys_agent.domain import SCHEMA_VERSION, Envelope, Source, build_subject


def test_build_subject_uses_source() -> None:
    assert build_subject("oopsys", "agent-1", Source.SERVER) == "oopsys.agents.agent-1.server"


def test_build_subject_respects_prefix() -> None:
    assert build_subject("custom", "a", Source.DOCKER) == "custom.agents.a.docker"


def test_envelope_defaults_schema_version() -> None:
    envelope = Envelope(agent_id="a", source=Source.AGENT, payload={"k": "v"})
    assert envelope.schema_version == SCHEMA_VERSION
    assert envelope.payload == {"k": "v"}
