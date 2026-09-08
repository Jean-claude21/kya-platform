"""Add non-secret connector configuration to governed data sources."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0012"
down_revision: str | None = "20260907_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source",
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema="data",
    )
    op.alter_column("source", "configuration", server_default=None, schema="data")


def downgrade() -> None:
    op.drop_column("source", "configuration", schema="data")
