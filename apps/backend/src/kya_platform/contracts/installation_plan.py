"""Deterministic, secret-free plans for client-consented artifact installation."""

from enum import StrEnum
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field

from kya_platform.contracts.artifact_manifest import ArtifactType


class InstallationProfile(StrEnum):
    CODEX = "codex"
    CLAUDE_CODE = "claude-code"
    PORTABLE_ZIP = "portable-zip"


class InstallationScope(StrEnum):
    PERSONAL = "personal"
    PROJECT = "project"


class InstallationAction(StrEnum):
    FETCH = "fetch-package"
    VERIFY_SIGNATURE = "verify-release-signature"
    VERIFY_DIGEST = "verify-content-digest"
    VERIFY_COMPATIBILITY = "verify-client-compatibility"
    STAGE = "stage-files"
    ACTIVATE = "activate-atomically"
    WRITE_RECEIPT = "write-installation-receipt"


class ClientCompatibilityError(ValueError):
    """The client cannot safely consume the selected release."""


class InstallationStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order: int = Field(ge=1)
    action: InstallationAction
    source: str | None = None
    destination: str | None = None
    expected_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class InstallationPlan(BaseModel):
    """Instructions for a trusted client; the KYA server never executes these steps."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    plan_id: UUID
    release_id: UUID
    artifact_id: UUID
    artifact_type: ArtifactType
    artifact_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    version: str
    profile: InstallationProfile
    scope: InstallationScope
    target: str = Field(min_length=1, max_length=200)
    destination: str
    package_locator: str
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    compatibility_requirement: str
    client_version: str
    file_count: int = Field(ge=1)
    package_size: int = Field(ge=1)
    steps: tuple[InstallationStep, ...] = Field(min_length=7, max_length=7)
    requires_client_confirmation: Literal[True] = True
    server_writes_local_files: Literal[False] = False


def destination_for(
    profile: InstallationProfile,
    scope: InstallationScope,
    slug: str,
    version: str,
) -> str:
    """Return a symbolic destination that only the authenticated client resolves."""

    if profile is InstallationProfile.CODEX:
        root = (
            "${CODEX_PERSONAL_SKILLS_DIR}"
            if scope is InstallationScope.PERSONAL
            else ".agents/skills"
        )
        return f"{root}/{slug}"
    if profile is InstallationProfile.CLAUDE_CODE:
        root = "~/.claude/skills" if scope is InstallationScope.PERSONAL else ".claude/skills"
        return f"{root}/{slug}"
    return f"${{USER_SELECTED_DIRECTORY}}/{slug}-{version}.zip"


def build_installation_plan(
    *,
    release_id: UUID,
    artifact_id: UUID,
    artifact_type: ArtifactType,
    artifact_slug: str,
    version: str,
    profile: InstallationProfile,
    scope: InstallationScope,
    target: str,
    package_locator: str,
    content_digest: str,
    compatibility_requirement: str,
    client_version: str,
    file_count: int,
    package_size: int,
) -> InstallationPlan:
    """Build the same plan for the same immutable release and target."""

    if profile is not InstallationProfile.PORTABLE_ZIP and artifact_type is not ArtifactType.SKILL:
        raise ValueError("Codex and Claude Code filesystem profiles currently accept Skills only")
    if not package_locator.startswith(("git+https://", "https://", "oci://")):
        raise ValueError("release package locator is not supported")
    try:
        compatible = Version(client_version) in SpecifierSet(compatibility_requirement)
    except (InvalidSpecifier, InvalidVersion) as error:
        raise ClientCompatibilityError("release compatibility policy is invalid") from error
    if not compatible:
        raise ClientCompatibilityError(
            "client version does not satisfy the release compatibility policy"
        )
    destination = destination_for(profile, scope, artifact_slug, version)
    identity = "|".join(
        (
            str(release_id),
            profile.value,
            scope.value,
            target,
            destination,
            content_digest,
            client_version,
        )
    )
    plan_id = uuid5(NAMESPACE_URL, f"https://kya.energy/install-plan/v1/{identity}")
    stage = f"${{KYA_STAGING_DIR}}/{plan_id}"
    receipt = f"${{KYA_RECEIPTS_DIR}}/{plan_id}.json"
    return InstallationPlan(
        plan_id=plan_id,
        release_id=release_id,
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_slug=artifact_slug,
        version=version,
        profile=profile,
        scope=scope,
        target=target,
        destination=destination,
        package_locator=package_locator,
        content_digest=content_digest,
        compatibility_requirement=compatibility_requirement,
        client_version=client_version,
        file_count=file_count,
        package_size=package_size,
        steps=(
            InstallationStep(order=1, action=InstallationAction.FETCH, source=package_locator),
            InstallationStep(
                order=2,
                action=InstallationAction.VERIFY_SIGNATURE,
                expected_digest=content_digest,
            ),
            InstallationStep(
                order=3,
                action=InstallationAction.VERIFY_DIGEST,
                expected_digest=content_digest,
            ),
            InstallationStep(order=4, action=InstallationAction.VERIFY_COMPATIBILITY),
            InstallationStep(order=5, action=InstallationAction.STAGE, destination=stage),
            InstallationStep(
                order=6,
                action=InstallationAction.ACTIVATE,
                source=stage,
                destination=destination,
            ),
            InstallationStep(
                order=7,
                action=InstallationAction.WRITE_RECEIPT,
                destination=receipt,
                expected_digest=content_digest,
            ),
        ),
    )


__all__ = [
    "ClientCompatibilityError",
    "InstallationAction",
    "InstallationPlan",
    "InstallationProfile",
    "InstallationScope",
    "InstallationStep",
    "build_installation_plan",
    "destination_for",
]
