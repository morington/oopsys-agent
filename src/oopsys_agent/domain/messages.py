from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from oopsys_agent.domain.enums import Source

SCHEMA_VERSION = 1


def build_subject(prefix: str, agent_id: str, source: Source) -> str:
    return f"{prefix}.agents.{agent_id}.{source.value}"


class Envelope(BaseModel):
    schema_version: int = SCHEMA_VERSION
    agent_id: str
    source: Source
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    payload: dict[str, Any]
