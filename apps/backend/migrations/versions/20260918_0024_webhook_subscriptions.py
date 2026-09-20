"""Persist governed webhook subscriptions.

Revision ID: 20260918_0024
Revises: 20260918_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260918_0024"
down_revision: str | None = "20260918_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscription",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_scope", sa.String(length=255), nullable=False),
        sa.Column("endpoint_url", sa.String(length=2048), nullable=False),
        sa.Column("event_types", postgresql.ARRAY(sa.String(length=160)), nullable=False),
        sa.Column("secret_reference_id", sa.Uuid(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="reliability",
    )
    op.create_index(
        "ix_webhook_subscription_scope_enabled",
        "webhook_subscription",
        ["owner_scope", "is_enabled"],
        schema="reliability",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_webhook_subscription_scope_enabled",
        table_name="webhook_subscription",
        schema="reliability",
    )
    op.drop_table("webhook_subscription", schema="reliability")
