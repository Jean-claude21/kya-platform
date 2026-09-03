"""Versioned manifest shared by every distributable KYA artifact."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator

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

    @field_validator("scopes")
    @classmethod
    def validate_unique_scopes(cls, scopes: list[str]) -> list[str]:
        if len(scopes) != len(set(scopes)):
            raise ValueError("Scopes must be unique")
        return scopes


__all__ = [
    "ArtifactDependency",
    "ArtifactIntegrity",
    "ArtifactManifest",
    "ArtifactOwners",
    "ArtifactSource",
    "ArtifactType",
    "RiskLevel",
]
