"""Shared SQLAlchemy mapping conventions."""

from uuid import UUID, uuid7

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(AsyncAttrs, DeclarativeBase):
    """Base for backend-owned relational models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def new_id() -> UUID:
    """Generate a time-ordered RFC 9562 identifier."""

    return uuid7()


__all__ = ["Base", "new_id"]
