from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from oopsys_agent.domain.enums import Severity


class ErrorReport(BaseModel):
    severity: Severity
    service: str
    environment: str
    exception_type: str
    message: str
    traceback: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    context: dict[str, Any] = Field(default_factory=dict)
