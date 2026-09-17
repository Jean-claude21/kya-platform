"""Strict Registry MCP schemas and two-layer tool authorization."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kya_platform.application.reliability import JsonValue
from kya_platform.authorization import (
    AuthorizationService,
    CheckRequest,
    ContextualTuple,
    ListObjectsRequest,
)
from kya_platform.contracts.artifact_manifest import ArtifactType
from kya_platform.contracts.artifact_package import PackageFileKind
from kya_platform.contracts.installation_plan import (
    InstallationPlan,
    InstallationProfile,
    InstallationScope,
)

NonEmpty = Annotated[str, Field(min_length=1)]
IdempotencyKey = Annotated[str, Field(min_length=16, max_length=200)]


class StrictMcpContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Confirmation(StrictMcpContract):
    confirmed: Literal[True]


class SearchCatalogInput(StrictMcpContract):
    query: str = Field(default="", max_length=200)
    types: tuple[ArtifactType, ...] = ()
    workspace: str | None = None
    cursor: str | None = None


class GetArtifactInput(StrictMcpContract):
    artifact_id: NonEmpty
    version: str | None = None


class ListUpdatesInput(StrictMcpContract):
    installation_id: UUID


class RequestInstallInput(StrictMcpContract):
    release_id: UUID
    target: NonEmpty
    profile: InstallationProfile
    scope: InstallationScope
    client_version: NonEmpty
    idempotency_key: IdempotencyKey
    confirmation: Confirmation


class ConfirmInstallationInput(StrictMcpContract):
    plan_id: UUID
    release_id: UUID
    target: NonEmpty
    profile: InstallationProfile
    scope: InstallationScope
    client_version: NonEmpty
    installed_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    actor_id: UUID
    idempotency_key: IdempotencyKey
    confirmation: Confirmation


class RequestUpdateInput(StrictMcpContract):
    installation_id: UUID
    release_id: UUID
    actor_id: UUID
    idempotency_key: IdempotencyKey
    confirmation: Confirmation


class ConfirmUpdateInput(StrictMcpContract):
    operation_id: UUID
    installed_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    expected_revision: int = Field(ge=1)
    actor_id: UUID
    confirmation: Confirmation


class InstallationAction(StrEnum):
    ROLLBACK = "rollback"
    SUSPEND = "suspend"
    RESUME = "resume"
    REVOKE = "revoke"


class ManageInstallationInput(StrictMcpContract):
    installation_id: UUID
    action: InstallationAction
    expected_revision: int = Field(ge=1)
    actor_id: UUID
    reason: str | None = Field(default=None, max_length=500)
    idempotency_key: IdempotencyKey
    confirmation: Confirmation


class GetOperationInput(StrictMcpContract):
    operation_id: UUID


class PublishCandidateInput(StrictMcpContract):
    artifact_id: NonEmpty
    version: NonEmpty
    evidence: tuple[NonEmpty, ...] = Field(min_length=1)
    actor_id: UUID
    idempotency_key: IdempotencyKey
    confirmation: Confirmation


class ArtifactProposalFile(StrictMcpContract):
    path: str = Field(min_length=1, max_length=512)
    kind: PackageFileKind
    content: str | None = Field(default=None, max_length=2_000_000)
    content_base64: str | None = Field(default=None, max_length=2_700_000)

    @model_validator(mode="after")
    def require_one_content_representation(self) -> ArtifactProposalFile:
        if (self.content is None) == (self.content_base64 is None):
            raise ValueError("provide exactly one of content or content_base64")
        return self


class SubmitArtifactProposalInput(StrictMcpContract):
    target_workspace: NonEmpty
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,119}$")
    artifact_type: ArtifactType
    files: tuple[ArtifactProposalFile, ...] = Field(min_length=1, max_length=256)
    artifact_id: str | None = None
    idempotency_key: IdempotencyKey
    confirmation: Confirmation


class ArtifactSummary(StrictMcpContract):
    artifact_id: str
    artifact_type: ArtifactType
    name: str
    summary: str | None = None
    latest_version: str | None = None
    owner_workspace_id: str | None = None
    visibility: str | None = None
    visibility_scope_unit_id: str | None = None
    effective_permissions: tuple[Literal["view"], ...] = ("view",)


class SearchCatalogOutput(StrictMcpContract):
    items: tuple[ArtifactSummary, ...]
    next_cursor: str | None = None


class ArtifactDetail(ArtifactSummary):
    lifecycle: str
    versions: tuple[str, ...]
    installable: bool


class UpdateSummary(StrictMcpContract):
    installation_id: UUID
    current_version: str
    candidate_version: str
    decision: Literal["propose", "require-approval", "expedited-approval", "block"]


class ListUpdatesOutput(StrictMcpContract):
    items: tuple[UpdateSummary, ...]


class OperationAccepted(StrictMcpContract):
    operation_id: UUID
    status: Literal["accepted"] = "accepted"


class InstallationRecorded(StrictMcpContract):
    installation_id: UUID
    operation_id: UUID
    status: Literal["active"] = "active"


class OperationStatus(StrictMcpContract):
    operation_id: UUID
    status: Literal["accepted", "pending", "running", "succeeded", "failed", "rolled-back"]
    error_code: str | None = None


class PublicationAccepted(StrictMcpContract):
    request_id: UUID
    status: Literal["submitted"] = "submitted"


class ArtifactProposalAccepted(StrictMcpContract):
    proposal_id: UUID
    status: Literal["submitted"] = "submitted"
    review_required: Literal[True] = True


class RegistryRisk(StrEnum):
    READ = "read"
    CONTROLLED_WRITE = "controlled-write"
    SENSITIVE_WRITE = "sensitive-write"


@dataclass(frozen=True, slots=True)
class RegistryTool:
    name: str
    oauth_scope: str
    permission: str
    object_type: str
    risk: RegistryRisk
    is_write: bool = False
    requires_confirmation: bool = False
    requires_idempotency_key: bool = False


REGISTRY_TOOLS: tuple[RegistryTool, ...] = (
    RegistryTool("search_catalog", "catalog:read", "can_view", "catalog", RegistryRisk.READ),
    RegistryTool("get_artifact", "catalog:read", "can_view", "artifact", RegistryRisk.READ),
    RegistryTool("list_updates", "catalog:read", "can_view", "workspace", RegistryRisk.READ),
    RegistryTool(
        "request_install",
        "catalog:install",
        "can_edit",
        "workspace",
        RegistryRisk.CONTROLLED_WRITE,
        True,
        True,
        True,
    ),
    RegistryTool(
        "confirm_installation",
        "catalog:install",
        "can_edit",
        "workspace",
        RegistryRisk.CONTROLLED_WRITE,
        True,
        True,
        True,
    ),
    RegistryTool(
        "request_update",
        "catalog:install",
        "can_edit",
        "workspace",
        RegistryRisk.CONTROLLED_WRITE,
        True,
        True,
        True,
    ),
    RegistryTool(
        "confirm_update",
        "catalog:install",
        "can_edit",
        "workspace",
        RegistryRisk.CONTROLLED_WRITE,
        True,
        True,
    ),
    RegistryTool(
        "manage_installation",
        "catalog:install",
        "can_manage",
        "workspace",
        RegistryRisk.SENSITIVE_WRITE,
        True,
        True,
        True,
    ),
    RegistryTool("get_operation", "catalog:read", "can_view", "workspace", RegistryRisk.READ),
    RegistryTool(
        "submit_artifact_proposal",
        "catalog:publish",
        # Proposing is intentionally available to every workspace viewer.  The
        # dedicated can_propose relation is equivalent in the current model,
        # but older production models do not expose it yet.
        "can_view",
        "workspace",
        RegistryRisk.SENSITIVE_WRITE,
        True,
        True,
        True,
    ),
    RegistryTool(
        "publish_candidate",
        "catalog:publish",
        "can_submit",
        "artifact",
        RegistryRisk.SENSITIVE_WRITE,
        True,
        True,
        True,
    ),
)


@dataclass(frozen=True, slots=True)
class ToolAccessContext:
    principal: str
    oauth_scopes: frozenset[str]
    resource: str
    authorization_context: Mapping[str, JsonValue]
    contextual_tuples: tuple[ContextualTuple, ...] = ()


class ToolAuthorizer:
    """Scopes narrow access; KYA authorization decides resource-level access."""

    def __init__(self, authorization: AuthorizationService) -> None:
        self._authorization = authorization

    async def is_allowed(self, tool: RegistryTool, context: ToolAccessContext) -> bool:
        if tool.oauth_scope not in context.oauth_scopes:
            return False
        evidence = await self._authorization.explain(
            CheckRequest(
                user=context.principal,
                relation=tool.permission,
                object=f"{tool.object_type}:{context.resource}",
                context=context.authorization_context,
                contextual_tuples=context.contextual_tuples,
            ),
            correlation_id=UUID(int=0),
        )
        return evidence.allowed

    async def allowed_artifact_ids(self, context: ToolAccessContext) -> tuple[str, ...]:
        if "catalog:read" not in context.oauth_scopes:
            return ()
        return await self._authorization.list_authorized_objects(
            ListObjectsRequest(
                user=context.principal,
                relation="can_view",
                object_type="artifact",
                context=context.authorization_context,
                contextual_tuples=context.contextual_tuples,
            )
        )

    async def visible_tools(self, context: ToolAccessContext) -> tuple[RegistryTool, ...]:
        visible: list[RegistryTool] = []
        for tool in REGISTRY_TOOLS:
            if await self.is_allowed(tool, context):
                visible.append(tool)
        return tuple(visible)


def assert_skills_are_resources() -> None:
    """Fail closed if a future tool accidentally makes a Skill executable."""

    if any("skill" in tool.name for tool in REGISTRY_TOOLS):
        raise RuntimeError("Skills must be distributed as artifacts, never executed as tools")


assert_skills_are_resources()

__all__ = [
    "REGISTRY_TOOLS",
    "ArtifactDetail",
    "ArtifactProposalAccepted",
    "ArtifactProposalFile",
    "ArtifactSummary",
    "ConfirmInstallationInput",
    "ConfirmUpdateInput",
    "Confirmation",
    "GetArtifactInput",
    "GetOperationInput",
    "InstallationAction",
    "InstallationPlan",
    "InstallationProfile",
    "InstallationRecorded",
    "InstallationScope",
    "ListUpdatesInput",
    "ListUpdatesOutput",
    "ManageInstallationInput",
    "OperationAccepted",
    "OperationStatus",
    "PublicationAccepted",
    "PublishCandidateInput",
    "RegistryRisk",
    "RegistryTool",
    "RequestInstallInput",
    "RequestUpdateInput",
    "SearchCatalogInput",
    "SearchCatalogOutput",
    "SubmitArtifactProposalInput",
    "ToolAccessContext",
    "ToolAuthorizer",
    "UpdateSummary",
]
