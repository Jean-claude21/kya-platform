"""Typed, digest-bound evidence required before artifact publication."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class AttestationKind(StrEnum):
    PROVENANCE = "provenance"
    SECRET_SCAN = "secret-scan"  # noqa: S105 - evidence kind, not a credential
    LICENSE = "license"
    COMPATIBILITY = "compatibility"
    BUSINESS_VALIDATION = "business-validation"
    TESTS = "tests"
    DEPENDENCY_SCAN = "dependency-scan"
    SBOM = "sbom"
    SECURITY = "security"


@dataclass(frozen=True, slots=True)
class AttestationRecord:
    id: UUID
    artifact_version_id: UUID
    kind: AttestationKind
    issuer_id: UUID
    subject_digest: str
    result: str
    valid_from: datetime
    valid_until: datetime | None
    evidence_uri: str


class AttestationRepository(Protocol):
    async def create(
        self,
        *,
        artifact_id: UUID,
        version_id: UUID,
        kind: AttestationKind,
        issuer_id: UUID,
        result: str,
        valid_from: datetime,
        valid_until: datetime | None,
        evidence_uri: str,
        correlation_id: UUID,
    ) -> AttestationRecord: ...


def required_attestation_kinds(
    *, risk: str, has_executable_content: bool
) -> frozenset[AttestationKind]:
    required = {
        AttestationKind.PROVENANCE,
        AttestationKind.SECRET_SCAN,
        AttestationKind.LICENSE,
        AttestationKind.COMPATIBILITY,
        AttestationKind.BUSINESS_VALIDATION,
    }
    if has_executable_content or risk != "read":
        required.update(
            {
                AttestationKind.TESTS,
                AttestationKind.DEPENDENCY_SCAN,
                AttestationKind.SBOM,
                AttestationKind.SECURITY,
            }
        )
    return frozenset(required)


__all__ = [
    "AttestationKind",
    "AttestationRecord",
    "AttestationRepository",
    "required_attestation_kinds",
]
