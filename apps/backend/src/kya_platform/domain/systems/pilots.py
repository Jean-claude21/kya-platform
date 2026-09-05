"""Fact-based pilot registrations used to validate the systems registry."""

from datetime import datetime
from uuid import UUID

from kya_platform.contracts.artifact_manifest import RiskLevel
from kya_platform.domain.organization import DateRange
from kya_platform.domain.systems import (
    ApprovedInterface,
    AvailabilityLevel,
    DataAuthority,
    InterfaceKind,
    RegisteredSystem,
    SystemCapability,
    SystemRegistry,
    SystemStatus,
)

KYA_PLATFORM_SYSTEM_ID = UUID("01991b0e-6a80-7000-8000-000000000001")
KYA_PLATFORM_AUTHORITY_ID = UUID("01991b0e-6a80-7000-8000-000000000002")


def kya_platform_pilot(*, effective_at: datetime) -> SystemRegistry:
    """Register only capabilities and data that KYA Platform already owns."""

    system = RegisteredSystem(
        id=KYA_PLATFORM_SYSTEM_ID,
        key="kya-platform",
        name="KYA Platform",
        business_owner="CVSI",
        technical_owner="Équipe Informatique et Logiciels",
        status=SystemStatus.ACTIVE,
        environments=frozenset({"preview"}),
        availability=AvailabilityLevel.CONTINUOUS,
        interfaces=(
            ApprovedInterface(
                name="Business API",
                kind=InterfaceKind.REST_API,
                contract_uri="/api/openapi.json",
                approved=True,
            ),
        ),
    )
    capability = SystemCapability(
        key="govern-artifacts",
        name="Gouverner les artefacts numériques KYA",
        provider_system_id=system.id,
        contract_uri="/api/openapi.json",
        risk=RiskLevel.ADMINISTRATIVE,
    )
    authority = DataAuthority(
        id=KYA_PLATFORM_AUTHORITY_ID,
        category_key="artifact-metadata",
        system_id=system.id,
        scope="group:kya",
        validity=DateRange(effective_at),
    )
    return SystemRegistry((system,), (capability,), (authority,))


__all__ = ["KYA_PLATFORM_SYSTEM_ID", "kya_platform_pilot"]
