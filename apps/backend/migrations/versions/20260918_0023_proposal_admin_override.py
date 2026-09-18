"""Audit principal-administrator proposal decision overrides.

Revision ID: 20260918_0023
Revises: 20260917_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0023"
down_revision: str | None = "20260917_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "proposal",
        sa.Column("administrative_override_by", sa.Uuid(), nullable=True),
        schema="catalog",
    )


def downgrade() -> None:
    op.drop_column("proposal", "administrative_override_by", schema="catalog")
