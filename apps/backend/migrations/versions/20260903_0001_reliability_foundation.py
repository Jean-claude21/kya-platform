"""Create reliability schemas and append-only audit evidence.

Revision ID: 20260903_0001
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260903_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")
    op.execute("CREATE SCHEMA IF NOT EXISTS reliability")

    op.create_table(
        "event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=160), nullable=False),
        sa.Column("target_type", sa.String(length=120), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=255), nullable=True),
        sa.Column("environment", sa.String(length=32), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("causation_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_event"),
        schema="audit",
    )
    op.create_index("ix_audit_event_target", "event", ["target_type", "target_id"], schema="audit")
    op.create_index("ix_audit_event_correlation", "event", ["correlation_id"], schema="audit")

    op.create_table(
        "outbox_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(length=160), nullable=False),
        sa.Column("aggregate_type", sa.String(length=120), nullable=False),
        sa.Column("aggregate_id", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_event"),
        schema="reliability",
    )
    op.create_index(
        "ix_reliability_outbox_pending",
        "outbox_event",
        ["processed_at", "available_at"],
        schema="reliability",
    )

    op.create_table(
        "idempotency_record",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_record"),
        sa.UniqueConstraint("scope", "idempotency_key", name="uq_idempotency_record_scope"),
        schema="reliability",
    )

    op.execute(
        """
        CREATE FUNCTION audit.reject_event_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'audit events are append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_event_append_only
        BEFORE UPDATE OR DELETE ON audit.event
        FOR EACH ROW EXECUTE FUNCTION audit.reject_event_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_event_append_only ON audit.event")
    op.execute("DROP FUNCTION IF EXISTS audit.reject_event_mutation()")
    op.drop_table("idempotency_record", schema="reliability")
    op.drop_index("ix_reliability_outbox_pending", table_name="outbox_event", schema="reliability")
    op.drop_table("outbox_event", schema="reliability")
    op.drop_index("ix_audit_event_correlation", table_name="event", schema="audit")
    op.drop_index("ix_audit_event_target", table_name="event", schema="audit")
    op.drop_table("event", schema="audit")
    op.execute("DROP SCHEMA IF EXISTS reliability")
    op.execute("DROP SCHEMA IF EXISTS audit")
