from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from oopsys_agent.database.base import Base, utc_now
from oopsys_agent.domain.enums import Severity


class AgentIdentity(Base):
    __tablename__ = "agent_identity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    agent_id: Mapped[str] = mapped_column(String(36), unique=True)
    token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    token_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    token_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ErrorReportRecord(Base):
    __tablename__ = "error_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    severity: Mapped[Severity] = mapped_column(String(16))
    service: Mapped[str] = mapped_column(String(255))
    environment: Mapped[str] = mapped_column(String(64))
    exception_type: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str] = mapped_column(Text)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ServerMetricRecord(Base):
    __tablename__ = "server_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cpu_percent: Mapped[float] = mapped_column(Float)
    mem_percent: Mapped[float] = mapped_column(Float)
    mem_used: Mapped[int] = mapped_column(Integer)
    mem_total: Mapped[int] = mapped_column(Integer)
    net_bytes_sent: Mapped[int] = mapped_column(Integer)
    net_bytes_recv: Mapped[int] = mapped_column(Integer)
    load_1: Mapped[float] = mapped_column(Float)
    load_5: Mapped[float] = mapped_column(Float)
    load_15: Mapped[float] = mapped_column(Float)
    disk_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ContainerStateRecord(Base):
    __tablename__ = "container_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    container_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    image: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    restarts: Mapped[int] = mapped_column(Integer, default=0)
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    mem_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    mem_usage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    net_rx: Mapped[int | None] = mapped_column(Integer, nullable=True)
    net_tx: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blk_read: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blk_write: Mapped[int | None] = mapped_column(Integer, nullable=True)
    labels: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AgentFaultRecord(Base):
    __tablename__ = "agent_faults"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    component: Mapped[str] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(128))
    exception_type: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str] = mapped_column(Text)
    severity: Mapped[Severity] = mapped_column(String(16), default=Severity.ERROR)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
