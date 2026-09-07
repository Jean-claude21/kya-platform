"""Database foundation tests that do not require external infrastructure."""

from uuid import UUID

import pytest

from kya_platform.infrastructure.database.base import Base, new_id
from kya_platform.infrastructure.database.bootstrap import _domain
from kya_platform.infrastructure.database.models import (
    AuditEvent,
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogAttestation,
    CatalogCapabilityManifest,
    CatalogPackageFile,
    CatalogPublicationRequest,
    CatalogRelease,
    CoreClientAccount,
    CoreExternalReference,
    CoreOrganizationalUnit,
    CoreOrganizationalUnitRelation,
    CoreOrganizationalUnitType,
    CoreParty,
    CoreProject,
    ExternalIdentity,
    IdempotencyRecord,
    OAuthClient,
    OAuthGrant,
    OAuthTokenRecord,
    OutboxEvent,
    PlatformBootstrapClaim,
)
from kya_platform.infrastructure.database.session import normalize_asyncpg_url


@pytest.mark.unit
def test_new_identifiers_are_uuid7_and_ordered() -> None:
    first = new_id()
    second = new_id()

    assert first.version == 7
    assert second.version == 7
    assert first < second


@pytest.mark.unit
def test_reliability_models_have_explicit_schema_ownership() -> None:
    assert AuditEvent.__table__.schema == "audit"
    assert OutboxEvent.__table__.schema == "reliability"
    assert IdempotencyRecord.__table__.schema == "reliability"
    assert set(Base.metadata.tables) == {
        "audit.event",
        "catalog.artifact",
        "catalog.artifact_version",
        "catalog.attestation",
        "catalog.capability_manifest",
        "catalog.distribution_operation",
        "catalog.installation",
        "catalog.installation_history",
        "catalog.package_file",
        "catalog.publication_request",
        "catalog.release",
        "core.client_account",
        "core.contact_point",
        "core.external_reference",
        "core.organizational_unit",
        "core.organizational_unit_relation",
        "core.organizational_unit_type",
        "core.party",
        "core.person_profile",
        "core.position",
        "core.position_assignment",
        "core.project",
        "core.project_site",
        "core.site",
        "core.work_relationship",
        "data.asset",
        "data.contract_version",
        "data.ingestion_run",
        "data.lineage_edge",
        "data.pipeline",
        "data.quality_result",
        "data.snapshot",
        "data.source",
        "identity.external_identity",
        "identity.platform_bootstrap_claim",
        "oauth.client",
        "oauth.grant",
        "oauth.token",
        "reliability.idempotency_record",
        "reliability.outbox_event",
    }
    assert OAuthClient.__table__.schema == "oauth"
    assert OAuthGrant.__table__.schema == "oauth"
    assert OAuthTokenRecord.__table__.schema == "oauth"


@pytest.mark.unit
def test_kya_core_models_have_explicit_ownership_and_stable_keys() -> None:
    assert CoreParty.__table__.schema == "core"
    assert CoreOrganizationalUnitType.__table__.schema == "core"
    assert CoreOrganizationalUnit.__table__.schema == "core"
    assert CoreOrganizationalUnitRelation.__table__.schema == "core"
    assert CoreClientAccount.__table__.schema == "core"
    assert CoreProject.__table__.schema == "core"
    assert CoreExternalReference.__table__.schema == "core"

    unit_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in CoreOrganizationalUnit.__table__.constraints
        if hasattr(constraint, "columns")
    }
    external_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in CoreExternalReference.__table__.constraints
        if hasattr(constraint, "columns")
    }
    assert ("key",) in unit_constraints
    assert ("system_key", "entity_type", "external_type", "external_id") in external_constraints


@pytest.mark.unit
def test_catalog_models_have_constraints_and_explicit_schema_ownership() -> None:
    assert CatalogArtifact.__table__.schema == "catalog"
    assert CatalogArtifactVersion.__table__.schema == "catalog"
    assert CatalogAttestation.__table__.schema == "catalog"
    assert CatalogPackageFile.__table__.schema == "catalog"
    assert CatalogCapabilityManifest.__table__.schema == "catalog"
    assert CatalogPublicationRequest.__table__.schema == "catalog"
    assert CatalogRelease.__table__.schema == "catalog"

    artifact_unique = {
        tuple(column.name for column in constraint.columns)
        for constraint in CatalogArtifact.__table__.constraints
        if hasattr(constraint, "columns")
    }
    version_unique = {
        tuple(column.name for column in constraint.columns)
        for constraint in CatalogArtifactVersion.__table__.constraints
        if hasattr(constraint, "columns")
    }
    assert ("registry_id", "slug") in artifact_unique
    assert ("artifact_id", "version") in version_unique


@pytest.mark.unit
def test_bootstrap_claim_row_maps_to_secret_free_domain_state() -> None:
    principal_id = UUID("01991fb0-6c00-7000-8000-000000000030")
    row = PlatformBootstrapClaim(
        key="platform-owner",
        principal_id=principal_id,
        owner_fingerprint="a" * 64,
        state="reserved",
    )

    claim = _domain(row)

    assert claim.principal_id == principal_id
    assert claim.owner_fingerprint == "a" * 64
    assert claim.state == "reserved"


@pytest.mark.unit
def test_idempotency_key_is_unique_inside_its_scope() -> None:
    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in IdempotencyRecord.__table__.constraints
        if hasattr(constraint, "columns")
    }

    assert ("scope", "idempotency_key") in constraint_columns


@pytest.mark.unit
def test_external_identity_is_unique_by_issuer_and_subject() -> None:
    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in ExternalIdentity.__table__.constraints
        if hasattr(constraint, "columns")
    }

    assert ExternalIdentity.__table__.schema == "identity"
    assert ("issuer", "subject") in constraint_columns


@pytest.mark.unit
def test_neon_connection_url_is_normalized_for_asyncpg() -> None:
    normalized = normalize_asyncpg_url(
        "postgresql://user:p%40ss@db.example/neondb"
        "?sslmode=require&channel_binding=require&application_name=kya"
    )

    assert normalized == (
        "postgresql+asyncpg://user:p%40ss@db.example/neondb?application_name=kya&ssl=require"
    )
    assert "channel_binding" not in normalized
    assert "sslmode" not in normalized


@pytest.mark.unit
def test_asyncpg_connection_url_preserves_existing_ssl_setting() -> None:
    normalized = normalize_asyncpg_url(
        "postgresql+asyncpg://user:password@db.example/neondb?ssl=verify-full&sslmode=require"
    )

    assert normalized.endswith("?ssl=verify-full")
