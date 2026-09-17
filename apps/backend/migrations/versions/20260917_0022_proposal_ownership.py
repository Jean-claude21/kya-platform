"""Persist proposal ownership assigned during review.

Revision ID: 20260917_0022
Revises: 20260916_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260917_0022"
down_revision: str | None = "20260916_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "proposal",
        sa.Column("business_owner_id", sa.Uuid(), nullable=True),
        schema="catalog",
    )
    op.add_column(
        "proposal",
        sa.Column("technical_owner_id", sa.Uuid(), nullable=True),
        schema="catalog",
    )


def downgrade() -> None:
    op.drop_column("proposal", "technical_owner_id", schema="catalog")
    op.drop_column("proposal", "business_owner_id", schema="catalog")
