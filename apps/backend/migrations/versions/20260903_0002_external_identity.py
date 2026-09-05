"""Create immutable external identity bindings.

Revision ID: 20260903_0002
Revises: 20260903_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_0002"
down_revision: str | None = "20260903_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS identity")
    op.create_table(
        "external_identity",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("issuer", sa.String(length=2048), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_external_identity"),
        sa.UniqueConstraint("issuer", "subject", name="uq_external_identity_subject"),
        schema="identity",
    )
    op.create_index(
        "ix_external_identity_principal",
        "external_identity",
        ["principal_id"],
        schema="identity",
    )
    op.execute(
        """
        CREATE FUNCTION identity.reject_external_identity_rebind() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.issuer IS DISTINCT FROM OLD.issuer
             OR NEW.subject IS DISTINCT FROM OLD.subject
             OR NEW.principal_id IS DISTINCT FROM OLD.principal_id THEN
            RAISE EXCEPTION 'external identities cannot be rebound';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_external_identity_no_rebind
        BEFORE UPDATE ON identity.external_identity
        FOR EACH ROW EXECUTE FUNCTION identity.reject_external_identity_rebind()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_external_identity_no_rebind ON identity.external_identity"
    )
    op.execute("DROP FUNCTION IF EXISTS identity.reject_external_identity_rebind()")
    op.drop_index(
        "ix_external_identity_principal",
        table_name="external_identity",
        schema="identity",
    )
    op.drop_table("external_identity", schema="identity")
    op.execute("DROP SCHEMA IF EXISTS identity")
