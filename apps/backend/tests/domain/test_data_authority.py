from datetime import UTC, datetime
from uuid import uuid4

import pytest

from kya_platform.contracts.artifact_manifest import RiskLevel
from kya_platform.domain.organization import DateRange
from kya_platform.domain.systems import (
    ApprovedInterface,
    AuthorityConflictError,
    AuthorityNotFoundError,
    AvailabilityLevel,
    DataAuthority,
    InterfaceKind,
    RegisteredSystem,
    SystemCapability,
    SystemRegistry,
    SystemStatus,
)


def at(day: int) -> datetime:
    return datetime(2026, 9, day, tzinfo=UTC)


def system(key: str) -> RegisteredSystem:
    return RegisteredSystem(
        id=uuid4(),
        key=key,
        name=key.upper(),
        business_owner="Direction métier",
        technical_owner="CVSI",
        status=SystemStatus.ACTIVE,
        environments=frozenset({"production"}),
        interfaces=(
            ApprovedInterface(
                "API métier",
                InterfaceKind.REST_API,
                f"catalog://contracts/{key}",
                approved=True,
            ),
        ),
        availability=AvailabilityLevel.BUSINESS_HOURS,
    )


@pytest.mark.unit
def test_frappe_can_be_the_explicit_authority_for_clients_without_copying_data() -> None:
    frappe = system("frappe-erpnext")
    authority = DataAuthority(uuid4(), "clients", frappe.id, "group:kya", DateRange(at(1)))
    registry = SystemRegistry(
        systems=(frappe,),
        capabilities=(
            SystemCapability(
                "client-read",
                "Lecture du référentiel clients",
                frappe.id,
                "catalog://contracts/frappe/client-read",
                RiskLevel.READ,
            ),
        ),
        authorities=(authority,),
    )

    resolved = registry.authority_for("clients", "group:kya", at=at(4))

    assert resolved.id == frappe.id
    assert not hasattr(authority, "records")


@pytest.mark.unit
def test_overlapping_exclusive_authorities_are_rejected() -> None:
    frappe = system("frappe-erpnext")
    crm = system("external-crm")

    with pytest.raises(AuthorityConflictError, match="overlap"):
        SystemRegistry(
            systems=(frappe, crm),
            authorities=(
                DataAuthority(uuid4(), "clients", frappe.id, "country:togo", DateRange(at(1))),
                DataAuthority(uuid4(), "clients", crm.id, "country:togo", DateRange(at(3))),
            ),
        )


@pytest.mark.unit
def test_historical_authority_handover_uses_half_open_periods() -> None:
    frappe = system("frappe-erpnext")
    crm = system("external-crm")
    registry = SystemRegistry(
        systems=(frappe, crm),
        authorities=(
            DataAuthority(uuid4(), "clients", frappe.id, "country:togo", DateRange(at(1), at(3))),
            DataAuthority(uuid4(), "clients", crm.id, "country:togo", DateRange(at(3))),
        ),
    )

    assert registry.authority_for("clients", "country:togo", at=at(2)).id == frappe.id
    assert registry.authority_for("clients", "country:togo", at=at(3)).id == crm.id


@pytest.mark.unit
def test_missing_authority_fails_closed() -> None:
    with pytest.raises(AuthorityNotFoundError, match="no active"):
        SystemRegistry((system("frappe-erpnext"),)).authority_for(
            "clients", "country:benin", at=at(4)
        )


@pytest.mark.unit
def test_capability_cannot_reference_an_unknown_system() -> None:
    with pytest.raises(ValueError, match="provider"):
        SystemRegistry(
            systems=(system("frappe-erpnext"),),
            capabilities=(
                SystemCapability(
                    "client-read",
                    "Lecture clients",
                    uuid4(),
                    "catalog://contracts/frappe/client-read",
                    RiskLevel.READ,
                ),
            ),
        )
