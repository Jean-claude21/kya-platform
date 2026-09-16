"""Use Filiale as the governed label for legal entities.

Revision ID: 20260916_0021
Revises: 20260912_0020
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260916_0021"
down_revision: str | None = "20260912_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Keep the stable key `entity` because it is already referenced by units and policies. The
    # governed vocabulary is a label, not a destructive identifier migration.
    op.execute(
        """
        UPDATE core.organizational_unit_type
        SET label = 'Filiale'
        WHERE key = 'entity'
        """
    )
    # Direct Group and country parents remain accepted during the transition. New administration
    # guidance prefers Filiale as the legal/operational parent and treats country_code as geography.
    op.execute(
        """
        UPDATE core.organizational_unit_type
        SET allowed_parent_types = ARRAY['group', 'country', 'entity']::varchar[]
        WHERE key = 'agency'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE core.organizational_unit_type
        SET label = 'Entité'
        WHERE key = 'entity'
        """
    )
    op.execute(
        """
        UPDATE core.organizational_unit_type
        SET allowed_parent_types = ARRAY['country', 'entity']::varchar[]
        WHERE key = 'agency'
        """
    )
