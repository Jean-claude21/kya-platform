"""Add persistent state for the KYA OAuth broker.

Revision ID: 20260907_0007
Revises: 20260906_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0007"
down_revision: str | None = "20260906_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS oauth")
    op.create_table(
        "client",
        sa.Column("client_id", sa.String(length=128), primary_key=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("encrypted_secret", sa.LargeBinary(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="oauth",
    )
    op.create_table(
        "grant",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("code_digest", sa.String(length=64), nullable=True),
        sa.Column("client_id", sa.String(length=128), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("redirect_uri_explicit", sa.Boolean(), nullable=False),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("active_unit_id", sa.String(length=512), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("denied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["client_id"], ["oauth.client.client_id"], ondelete="CASCADE"),
        schema="oauth",
    )
    op.create_index(
        "ix_oauth_grant_request_digest", "grant", ["request_digest"], unique=True, schema="oauth"
    )
    op.create_index(
        "ix_oauth_grant_code_digest", "grant", ["code_digest"], unique=True, schema="oauth"
    )
    op.create_table(
        "token",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", sa.String(length=128), nullable=False),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active_unit_id", sa.String(length=512), nullable=False),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["grant_id"], ["oauth.grant.id"], ondelete="CASCADE"),
        schema="oauth",
    )
    op.create_index("ix_oauth_token_digest", "token", ["token_digest"], unique=True, schema="oauth")
    op.create_index("ix_oauth_token_grant", "token", ["grant_id"], schema="oauth")


def downgrade() -> None:
    op.drop_table("token", schema="oauth")
    op.drop_table("grant", schema="oauth")
    op.drop_table("client", schema="oauth")
    op.execute("DROP SCHEMA IF EXISTS oauth")
