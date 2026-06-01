from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from structlog import getLogger

from oopsys_agent.configuration.loggers import Loggers

logger = getLogger(Loggers.development.name)


class ApplicationModel(BaseModel):
    host: str = Field(default="0.0.0.0")  # noqa: S104  # nosec B104
    port: int = Field(default=8080, ge=1, le=65535)

    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class SqliteModel(BaseModel):
    path: str = Field(default="data/oopsys-agent.db")
    driver: str = Field(default="sqlite+aiosqlite")

    def url(self) -> str:
        return f"{self.driver}:///{self.path}"


class NatsModel(BaseModel):
    enabled: bool = Field(default=True)
    servers: list[str] = Field(default_factory=lambda: ["nats://localhost:4222"])
    stream: str = Field(default="OOPSYS")
    subject_prefix: str = Field(default="oopsys")
    connect_timeout: float = Field(default=5.0, gt=0)
    publish_timeout: float = Field(default=5.0, gt=0)


class IntervalsModel(BaseModel):
    metrics_seconds: float = Field(default=30.0, gt=0)
    publish_seconds: float = Field(default=5.0, gt=0)
    retry_base_seconds: float = Field(default=5.0, gt=0)
    retry_max_seconds: float = Field(default=300.0, gt=0)


class AgentModel(BaseModel):
    name: str = Field(default="oopsys-agent")
    token: str | None = Field(default=None)


class Configuration(BaseSettings):
    is_development: bool = Field(default=False, alias="DEV")

    application: ApplicationModel = ApplicationModel()
    sqlite: SqliteModel = SqliteModel()
    nats: NatsModel = NatsModel()
    intervals: IntervalsModel = IntervalsModel()
    agent: AgentModel = AgentModel()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    @model_validator(mode="after")
    def warn_development(self) -> "Configuration":
        if self.is_development:
            logger.warning("Application started in development mode")
        return self
