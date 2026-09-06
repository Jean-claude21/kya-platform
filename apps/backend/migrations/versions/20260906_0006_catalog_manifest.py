"""Persist the complete validated artifact manifest.

Revision ID: 20260906_0006
Revises: 20260906_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260906_0006"
down_revision: str | None = "20260906_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "artifact_version",
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="catalog",
    )
    op.execute(
        "ALTER TABLE catalog.artifact_version "
        "DISABLE TRIGGER trg_catalog_published_version_immutable"
    )
    op.execute(
        """
        UPDATE catalog.artifact_version AS version
        SET manifest = jsonb_build_object(
            'schemaVersion', '1',
            'id', 'kya:' || artifact.artifact_type || ':' || artifact.slug,
            'type', artifact.artifact_type,
            'name', artifact.name,
            'version', version.version,
            'summary', artifact.summary,
            'owners', jsonb_build_object(
                'business', artifact.business_owner_id::text,
                'technical', artifact.technical_owner_id::text,
                'workspace', artifact.owner_workspace_id::text
            ),
            'source', jsonb_build_object(
                'repository', version.source_repository,
                'commit', version.source_commit,
                'path', version.source_path
            ),
            'integrity', jsonb_build_object(
                'algorithm', 'sha256',
                'digest', version.content_digest
            ),
            'compatibility', '{}'::jsonb,
            'dependencies', '[]'::jsonb,
            'scopes', '[]'::jsonb,
            'risk', version.risk
        )
        FROM catalog.artifact AS artifact
        WHERE version.artifact_id = artifact.id AND version.manifest IS NULL
        """
    )
    op.execute(
        "ALTER TABLE catalog.artifact_version "
        "ENABLE TRIGGER trg_catalog_published_version_immutable"
    )
    op.alter_column("artifact_version", "manifest", nullable=False, schema="catalog")


def downgrade() -> None:
    op.drop_column("artifact_version", "manifest", schema="catalog")
