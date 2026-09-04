"""Add durable outbox worker leases and retry evidence.

Revision ID: 20260904_0003
Revises: 20260903_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_0003"
down_revision: str | None = "20260903_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outbox_event",
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        schema="reliability",
    )
    op.add_column(
        "outbox_event",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        schema="reliability",
    )
    op.add_column(
        "outbox_event",
        sa.Column("last_error", sa.String(length=256), nullable=True),
        schema="reliability",
    )
    op.add_column(
        "outbox_event",
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        schema="reliability",
    )
    op.create_index(
        "ix_reliability_outbox_leaseable",
        "outbox_event",
        ["processed_at", "dead_lettered_at", "available_at", "lease_expires_at"],
        schema="reliability",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reliability_outbox_leaseable", table_name="outbox_event", schema="reliability"
    )
    op.drop_column("outbox_event", "dead_lettered_at", schema="reliability")
    op.drop_column("outbox_event", "last_error", schema="reliability")
    op.drop_column("outbox_event", "lease_expires_at", schema="reliability")
    op.drop_column("outbox_event", "lease_owner", schema="reliability")
