from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, mapped_column


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


class Base(DeclarativeBase):
    pass


def timestamp_column(*, default: bool = True):
    if default:
        return mapped_column(DateTime(timezone=True), default=utc_now)
    return mapped_column(DateTime(timezone=True), nullable=True)
