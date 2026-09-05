"""Database foundation tests that do not require external infrastructure."""

import pytest

from kya_platform.infrastructure.database.base import Base, new_id
from kya_platform.infrastructure.database.models import (
    AuditEvent,
    ExternalIdentity,
    IdempotencyRecord,
    OutboxEvent,
)
from kya_platform.infrastructure.database.session import normalize_asyncpg_url


@pytest.mark.unit
def test_new_identifiers_are_uuid7_and_ordered() -> None:
    first = new_id()
    second = new_id()

    assert first.version == 7
    assert second.version == 7
    assert first < second


@pytest.mark.unit
def test_reliability_models_have_explicit_schema_ownership() -> None:
    assert AuditEvent.__table__.schema == "audit"
    assert OutboxEvent.__table__.schema == "reliability"
    assert IdempotencyRecord.__table__.schema == "reliability"
    assert set(Base.metadata.tables) == {
        "audit.event",
        "identity.external_identity",
        "reliability.idempotency_record",
        "reliability.outbox_event",
    }


@pytest.mark.unit
def test_idempotency_key_is_unique_inside_its_scope() -> None:
    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in IdempotencyRecord.__table__.constraints
        if hasattr(constraint, "columns")
    }

    assert ("scope", "idempotency_key") in constraint_columns


@pytest.mark.unit
def test_external_identity_is_unique_by_issuer_and_subject() -> None:
    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in ExternalIdentity.__table__.constraints
        if hasattr(constraint, "columns")
    }

    assert ExternalIdentity.__table__.schema == "identity"
    assert ("issuer", "subject") in constraint_columns


@pytest.mark.unit
def test_neon_connection_url_is_normalized_for_asyncpg() -> None:
    normalized = normalize_asyncpg_url(
        "postgresql://user:p%40ss@db.example/neondb"
        "?sslmode=require&channel_binding=require&application_name=kya"
    )

    assert normalized == (
        "postgresql+asyncpg://user:p%40ss@db.example/neondb"
        "?application_name=kya&ssl=require"
    )
    assert "channel_binding" not in normalized
    assert "sslmode" not in normalized


@pytest.mark.unit
def test_asyncpg_connection_url_preserves_existing_ssl_setting() -> None:
    normalized = normalize_asyncpg_url(
        "postgresql+asyncpg://user:password@db.example/neondb"
        "?ssl=verify-full&sslmode=require"
    )

    assert normalized.endswith("?ssl=verify-full")
