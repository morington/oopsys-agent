import traceback as tb_module
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from oopsys_agent.domain.enums import Severity


class AgentFault(BaseModel):
    component: str
    operation: str
    exception_type: str
    message: str
    traceback: str
    severity: Severity = Severity.ERROR
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    @classmethod
    def from_exception(
        cls,
        exc: BaseException,
        *,
        component: str,
        operation: str,
        severity: Severity = Severity.ERROR,
    ) -> "AgentFault":
        tb = "".join(tb_module.format_exception(type(exc), exc, exc.__traceback__))
        return cls(
            component=component,
            operation=operation,
            exception_type=type(exc).__name__,
            message=str(exc) or type(exc).__name__,
            traceback=tb,
            severity=severity,
        )
