"""Deterministic installation, update and rollback decisions."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ChangeKind(StrEnum):
    SECURITY = "security"
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


class UpdateDecision(StrEnum):
    PROPOSE = "propose"
    REQUIRE_APPROVAL = "require-approval"
    EXPEDITED_APPROVAL = "expedited-approval"
    BLOCK = "block"


class ReleaseAvailability(StrEnum):
    PUBLISHED = "published"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class InstallationStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class UpdatePolicy:
    automatically_propose_patches: bool = True


class DistributionRuleError(ValueError):
    """A release cannot safely transition the installation."""


@dataclass(frozen=True, slots=True)
class ValidatedRelease:
    id: UUID
    artifact_id: UUID
    version: str
    content_digest: str
    integrity_verified: bool
    is_compatible: bool
    availability: ReleaseAvailability = ReleaseAvailability.PUBLISHED

    def require_safe(self) -> None:
        if not self.integrity_verified:
            raise DistributionRuleError("release integrity is not verified")
        if not self.is_compatible:
            raise DistributionRuleError("release is incompatible with the target")
        if self.availability is ReleaseAvailability.SUSPENDED:
            raise DistributionRuleError("release is suspended")
        if self.availability is ReleaseAvailability.REVOKED:
            raise DistributionRuleError("release is revoked")


@dataclass(frozen=True, slots=True)
class InstalledRelease:
    release_id: UUID
    version: str
    content_digest: str

    @classmethod
    def from_validated(cls, release: ValidatedRelease) -> InstalledRelease:
        return cls(release.id, release.version, release.content_digest)


@dataclass(frozen=True, slots=True)
class Installation:
    id: UUID
    artifact_id: UUID
    target: str
    active: InstalledRelease
    history: tuple[InstalledRelease, ...] = ()
    status: InstallationStatus = InstallationStatus.ACTIVE
    revision: int = 1

    @classmethod
    def install(cls, *, id: UUID, target: str, release: ValidatedRelease) -> Installation:
        release.require_safe()
        if not target:
            raise DistributionRuleError("installation target is required")
        return cls(id, release.artifact_id, target, InstalledRelease.from_validated(release))

    def update(
        self,
        release: ValidatedRelease,
        *,
        decision: UpdateDecision,
        approved: bool,
    ) -> Installation:
        if self.status is not InstallationStatus.ACTIVE:
            raise DistributionRuleError("only an active installation can be updated")
        release.require_safe()
        if release.artifact_id != self.artifact_id:
            raise DistributionRuleError("release belongs to another artifact")
        if release.id == self.active.release_id:
            return self
        if decision is UpdateDecision.BLOCK:
            raise DistributionRuleError("update policy blocks this release")
        if decision is not UpdateDecision.PROPOSE and not approved:
            raise DistributionRuleError("update approval is required")
        return Installation(
            self.id,
            self.artifact_id,
            self.target,
            InstalledRelease.from_validated(release),
            (*self.history, self.active),
            InstallationStatus.ACTIVE,
            self.revision + 1,
        )

    def rollback(self, *, expected_release_id: UUID | None = None) -> Installation:
        if not self.history:
            raise DistributionRuleError("no last-known-good release is available")
        previous = self.history[-1]
        if expected_release_id is not None and previous.release_id != expected_release_id:
            raise DistributionRuleError("rollback target is not the last-known-good release")
        return Installation(
            self.id,
            self.artifact_id,
            self.target,
            previous,
            self.history[:-1],
            InstallationStatus.ACTIVE,
            self.revision + 1,
        )

    def suspend(self) -> Installation:
        if self.status is InstallationStatus.REVOKED:
            raise DistributionRuleError("a revoked installation cannot be suspended")
        if self.status is InstallationStatus.SUSPENDED:
            return self
        return Installation(
            self.id,
            self.artifact_id,
            self.target,
            self.active,
            self.history,
            InstallationStatus.SUSPENDED,
            self.revision + 1,
        )

    def resume(self) -> Installation:
        if self.status is InstallationStatus.REVOKED:
            raise DistributionRuleError("a revoked installation cannot be resumed")
        if self.status is InstallationStatus.ACTIVE:
            return self
        return Installation(
            self.id,
            self.artifact_id,
            self.target,
            self.active,
            self.history,
            InstallationStatus.ACTIVE,
            self.revision + 1,
        )

    def revoke(self) -> Installation:
        if self.status is InstallationStatus.REVOKED:
            return self
        return Installation(
            self.id,
            self.artifact_id,
            self.target,
            self.active,
            self.history,
            InstallationStatus.REVOKED,
            self.revision + 1,
        )


def assess_update(policy: UpdatePolicy, *, kind: ChangeKind, is_compatible: bool) -> UpdateDecision:
    if not is_compatible:
        return UpdateDecision.BLOCK
    if kind is ChangeKind.SECURITY:
        return UpdateDecision.EXPEDITED_APPROVAL
    if kind is ChangeKind.PATCH and policy.automatically_propose_patches:
        return UpdateDecision.PROPOSE
    return UpdateDecision.REQUIRE_APPROVAL


__all__ = [
    "ChangeKind",
    "DistributionRuleError",
    "Installation",
    "InstallationStatus",
    "InstalledRelease",
    "ReleaseAvailability",
    "UpdateDecision",
    "UpdatePolicy",
    "ValidatedRelease",
    "assess_update",
]
