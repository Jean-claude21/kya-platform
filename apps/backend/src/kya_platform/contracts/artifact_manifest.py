"""Versioned manifest shared by every distributable KYA artifact."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

ARTIFACT_ID_PATTERN = r"^kya:[a-z0-9-]+:[a-z0-9][a-z0-9-]*$"
SEMVER_PATTERN = (
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?$"
)
COMMIT_PATTERN = r"^[a-fA-F0-9]{40}$"
DIGEST_PATTERN = r"^[a-fA-F0-9]{64}$"

NonEmptyText = Annotated[str, Field(min_length=1)]


class StrictContract(BaseModel):
    """Reject undeclared fields at every contract level."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ArtifactType(StrEnum):
    APP = "app"
    SYSTEM = "system"
    API = "api"
    DATA_PRODUCT = "data-product"
    MCP_SERVER = "mcp-server"
    MCP_TOOL = "mcp-tool"
    SKILL = "skill"
    TEMPLATE = "template"
    MODEL = "model"
    DESIGN_SYSTEM = "design-system"
    CONNECTOR = "connector"
    POLICY = "policy"


class RiskLevel(StrEnum):
    READ = "read"
    CONTROLLED_WRITE = "controlled-write"
    SENSITIVE_WRITE = "sensitive-write"
    ADMINISTRATIVE = "administrative"


class CapabilityPermission(StrEnum):
    """Stable verbs shared by applications, MCP tools, skills and data products."""

    VIEW = "view"
    USE = "use"
    CREATE = "create"
    EDIT = "edit"
    ADMINISTER = "administer"
    PUBLISH = "publish"
    SHARE = "share"


class CapabilityScopeKind(StrEnum):
    """Organizational boundary at which a capability may be assigned."""

    PERSONAL = "personal"
    WORKSPACE = "workspace"
    UNIT = "unit"
    SUBSIDIARY = "subsidiary"
    GROUP = "group"


class CapabilityVisibility(StrEnum):
    PRIVATE = "private"
    RESTRICTED = "restricted"
    INTERNAL = "internal"
    PUBLIC = "public"


class ApplicationLaunchMode(StrEnum):
    SAME_TAB = "same-tab"
    NEW_TAB = "new-tab"
    EMBEDDED = "embedded"


class ArtifactOwners(StrictContract):
    business: NonEmptyText
    technical: NonEmptyText
    workspace: NonEmptyText


class ArtifactSource(StrictContract):
    repository: AnyUrl
    commit: str = Field(pattern=COMMIT_PATTERN)
    path: str | None = None


class ArtifactIntegrity(StrictContract):
    algorithm: Literal["sha256"]
    digest: str = Field(pattern=DIGEST_PATTERN)
    signature: str | None = None


class ArtifactDependency(StrictContract):
    artifact_id: NonEmptyText = Field(alias="id")
    version_range: NonEmptyText = Field(alias="range")
    optional: bool = False


class CapabilityFeature(StrictContract):
    key: str = Field(pattern=r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[CapabilityPermission] = Field(min_length=1)

    @field_validator("permissions")
    @classmethod
    def validate_unique_permissions(
        cls, permissions: list[CapabilityPermission]
    ) -> list[CapabilityPermission]:
        if len(permissions) != len(set(permissions)):
            raise ValueError("Feature permissions must be unique")
        return permissions


class CapabilityGovernance(StrictContract):
    visibility: CapabilityVisibility = CapabilityVisibility.RESTRICTED
    default_scope: CapabilityScopeKind = Field(alias="defaultScope")
    allowed_scopes: list[CapabilityScopeKind] = Field(alias="allowedScopes", min_length=1)
    permissions: list[CapabilityPermission] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_scope_and_permissions(self) -> CapabilityGovernance:
        if len(self.allowed_scopes) != len(set(self.allowed_scopes)):
            raise ValueError("Governance scopes must be unique")
        if self.default_scope not in self.allowed_scopes:
            raise ValueError("The default scope must be one of the allowed scopes")
        if len(self.permissions) != len(set(self.permissions)):
            raise ValueError("Governance permissions must be unique")
        return self


class ApplicationLaunch(StrictContract):
    url: AnyUrl
    mode: ApplicationLaunchMode = ApplicationLaunchMode.SAME_TAB
    icon_url: AnyUrl | None = Field(default=None, alias="iconUrl")
    health_url: AnyUrl | None = Field(default=None, alias="healthUrl")


class ApplicationDeclaration(StrictContract):
    launch: ApplicationLaunch
    required_sdk: str | None = Field(default=None, alias="requiredSdk")


class IntegrationDeclaration(StrictContract):
    """Machine-readable integration surface. It never carries credentials."""

    api_base_url: AnyUrl | None = Field(default=None, alias="apiBaseUrl")
    emits: list[str] = Field(default_factory=list)
    consumes: list[str] = Field(default_factory=list)
    webhooks: list[str] = Field(default_factory=list)
    mcp_tools: list[str] = Field(default_factory=list, alias="mcpTools")

    @field_validator("emits", "consumes", "webhooks", "mcp_tools")
    @classmethod
    def validate_unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Integration declarations must be unique")
        if any(not value.strip() for value in values):
            raise ValueError("Integration declarations cannot be empty")
        return values


class ArtifactManifest(StrictContract):
    """Immutable release metadata; never contains a secret value."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={"$id": "https://schemas.kya.energy/platform/artifact-manifest/v1"},
    )

    schema_version: Literal["1"] = Field(alias="schemaVersion")
    artifact_id: str = Field(alias="id", pattern=ARTIFACT_ID_PATTERN)
    artifact_type: ArtifactType = Field(alias="type")
    name: str = Field(min_length=2, max_length=120)
    version: str = Field(pattern=SEMVER_PATTERN)
    summary: str | None = Field(default=None, max_length=500)
    owners: ArtifactOwners
    source: ArtifactSource
    integrity: ArtifactIntegrity
    compatibility: dict[str, str]
    dependencies: list[ArtifactDependency] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    risk: RiskLevel = RiskLevel.READ
    governance: CapabilityGovernance | None = None
    features: list[CapabilityFeature] = Field(default_factory=list)
    application: ApplicationDeclaration | None = None
    integrations: IntegrationDeclaration = Field(default_factory=IntegrationDeclaration)

    @field_validator("scopes")
    @classmethod
    def validate_unique_scopes(cls, scopes: list[str]) -> list[str]:
        if len(scopes) != len(set(scopes)):
            raise ValueError("Scopes must be unique")
        return scopes

    @field_validator("features")
    @classmethod
    def validate_unique_features(cls, features: list[CapabilityFeature]) -> list[CapabilityFeature]:
        keys = [feature.key for feature in features]
        if len(keys) != len(set(keys)):
            raise ValueError("Feature keys must be unique")
        return features

    @model_validator(mode="after")
    def validate_type_specific_declarations(self) -> ArtifactManifest:
        expected_prefix = f"kya:{self.artifact_type.value}:"
        if not self.artifact_id.startswith(expected_prefix):
            raise ValueError("Artifact id type must match the manifest type")
        if self.application is not None and self.artifact_type is not ArtifactType.APP:
            raise ValueError("Only app artifacts may declare application launch metadata")
        return self


__all__ = [
    "ApplicationDeclaration",
    "ApplicationLaunch",
    "ApplicationLaunchMode",
    "ArtifactDependency",
    "ArtifactIntegrity",
    "ArtifactManifest",
    "ArtifactOwners",
    "ArtifactSource",
    "ArtifactType",
    "CapabilityFeature",
    "CapabilityGovernance",
    "CapabilityPermission",
    "CapabilityScopeKind",
    "CapabilityVisibility",
    "IntegrationDeclaration",
    "RiskLevel",
]
