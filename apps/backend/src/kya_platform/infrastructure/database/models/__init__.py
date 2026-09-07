"""Import every mapped model for Alembic discovery."""

from kya_platform.infrastructure.database.models.bootstrap import PlatformBootstrapClaim
from kya_platform.infrastructure.database.models.catalog import (
    CatalogArtifact,
    CatalogArtifactVersion,
    CatalogAttestation,
    CatalogCapabilityManifest,
    CatalogDistributionOperation,
    CatalogInstallation,
    CatalogInstallationHistory,
    CatalogPackageFile,
    CatalogPublicationRequest,
    CatalogRelease,
)
from kya_platform.infrastructure.database.models.core import (
    CoreClientAccount,
    CoreContactPoint,
    CoreExternalReference,
    CoreOrganizationalUnit,
    CoreOrganizationalUnitRelation,
    CoreOrganizationalUnitType,
    CoreParty,
    CorePersonProfile,
    CorePosition,
    CorePositionAssignment,
    CoreProject,
    CoreProjectSite,
    CoreSite,
    CoreWorkRelationship,
)
from kya_platform.infrastructure.database.models.identity import ExternalIdentity
from kya_platform.infrastructure.database.models.oauth import (
    OAuthClient,
    OAuthGrant,
    OAuthTokenRecord,
)
from kya_platform.infrastructure.database.models.reliability import (
    AuditEvent,
    IdempotencyRecord,
    OutboxEvent,
)

__all__ = [
    "AuditEvent",
    "CatalogArtifact",
    "CatalogArtifactVersion",
    "CatalogAttestation",
    "CatalogCapabilityManifest",
    "CatalogDistributionOperation",
    "CatalogInstallation",
    "CatalogInstallationHistory",
    "CatalogPackageFile",
    "CatalogPublicationRequest",
    "CatalogRelease",
    "CoreClientAccount",
    "CoreContactPoint",
    "CoreExternalReference",
    "CoreOrganizationalUnit",
    "CoreOrganizationalUnitRelation",
    "CoreOrganizationalUnitType",
    "CoreParty",
    "CorePersonProfile",
    "CorePosition",
    "CorePositionAssignment",
    "CoreProject",
    "CoreProjectSite",
    "CoreSite",
    "CoreWorkRelationship",
    "ExternalIdentity",
    "IdempotencyRecord",
    "OAuthClient",
    "OAuthGrant",
    "OAuthTokenRecord",
    "OutboxEvent",
    "PlatformBootstrapClaim",
]
