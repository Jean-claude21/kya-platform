"""Executable business rules for KYA's evolving organization."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.domain.organization import (
    AssignmentKind,
    DateRange,
    OrganizationalUnit,
    OrganizationalUnitRelation,
    OrganizationalUnitType,
    OrganizationGraph,
    Position,
    PositionAssignment,
    RelationKind,
)

ALICE = UUID("019914b2-1a40-7000-8000-000000000031")
GROUP = UUID("019914b2-1a40-7000-8000-000000000041")
TOGO = UUID("019914b2-1a40-7000-8000-000000000042")
CVSI = UUID("019914b2-1a40-7000-8000-000000000043")


def at(day: int) -> datetime:
    return datetime(2026, 9, day, tzinfo=UTC)


@pytest.mark.unit
def test_hierarchical_relation_rejects_a_cycle() -> None:
    graph = OrganizationGraph(
        units=(
            OrganizationalUnit(GROUP, "group", "group", "KYA-Energy Group", DateRange(at(1))),
            OrganizationalUnit(TOGO, "togo", "country", "KYA Togo", DateRange(at(1))),
            OrganizationalUnit(CVSI, "cvsi", "direction", "CVSI", DateRange(at(1))),
        ),
        relations=(
            OrganizationalUnitRelation(GROUP, TOGO, RelationKind.HIERARCHICAL, DateRange(at(1))),
            OrganizationalUnitRelation(TOGO, CVSI, RelationKind.HIERARCHICAL, DateRange(at(1))),
        ),
    )

    with pytest.raises(ValueError, match="cycle"):
        graph.with_relation(
            OrganizationalUnitRelation(CVSI, GROUP, RelationKind.HIERARCHICAL, DateRange(at(2)))
        )


@pytest.mark.unit
def test_move_keeps_history_and_changes_only_the_active_parent() -> None:
    graph = OrganizationGraph(
        units=(
            OrganizationalUnit(GROUP, "group", "group", "KYA-Energy Group", DateRange(at(1))),
            OrganizationalUnit(TOGO, "togo", "country", "KYA Togo", DateRange(at(1))),
            OrganizationalUnit(CVSI, "cvsi", "direction", "CVSI", DateRange(at(1))),
        ),
        relations=(
            OrganizationalUnitRelation(
                GROUP, CVSI, RelationKind.HIERARCHICAL, DateRange(at(1), at(10))
            ),
            OrganizationalUnitRelation(TOGO, CVSI, RelationKind.HIERARCHICAL, DateRange(at(10))),
        ),
    )

    assert graph.parent_ids(CVSI, at(5)) == (GROUP,)
    assert graph.parent_ids(CVSI, at(15)) == (TOGO,)


@pytest.mark.unit
def test_multiple_dated_assignments_coexist_without_deriving_permissions() -> None:
    position = Position(
        id=UUID("019914b2-1a40-7000-8000-000000000051"),
        key="head-software",
        name="Chef équipe informatique et logiciels",
        unit_id=CVSI,
        validity=DateRange(at(1)),
    )
    primary = PositionAssignment(
        id=UUID("019914b2-1a40-7000-8000-000000000061"),
        person_id=ALICE,
        position_id=position.id,
        scope_unit_id=CVSI,
        kind=AssignmentKind.PRIMARY,
        validity=DateRange(at(1)),
    )
    delegated = PositionAssignment(
        id=UUID("019914b2-1a40-7000-8000-000000000062"),
        person_id=ALICE,
        position_id=position.id,
        scope_unit_id=TOGO,
        kind=AssignmentKind.DELEGATION,
        validity=DateRange(at(10), at(20)),
        delegated_by=UUID("019914b2-1a40-7000-8000-000000000063"),
    )

    assert primary.is_active(at(15))
    assert delegated.is_active(at(15))
    assert not delegated.is_active(at(20))
    assert not hasattr(position, "permissions")


@pytest.mark.unit
def test_unit_types_are_configurable_without_free_form_identifiers() -> None:
    unit_type = OrganizationalUnitType(
        key="agency",
        label="Agence",
        allowed_parent_types=frozenset({"country", "entity"}),
    )

    assert unit_type.accepts_parent("country")
    assert not unit_type.accepts_parent("team")
    with pytest.raises(ValueError, match="key"):
        OrganizationalUnitType(key="Agence Lomé", label="Agence")


@pytest.mark.unit
def test_temporal_and_reference_invariants_fail_early() -> None:
    with pytest.raises(ValueError, match="timezone"):
        DateRange(datetime(2026, 9, 1))
    with pytest.raises(ValueError, match="after"):
        DateRange(at(2), at(1))
    with pytest.raises(ValueError, match="itself"):
        OrganizationalUnitRelation(GROUP, GROUP, RelationKind.TRANSVERSAL, DateRange(at(1)))

    unit = OrganizationalUnit(GROUP, "group", "group", "KYA", DateRange(at(1)))
    with pytest.raises(ValueError, match="unknown"):
        OrganizationGraph(
            units=(unit,),
            relations=(
                OrganizationalUnitRelation(GROUP, TOGO, RelationKind.TRANSVERSAL, DateRange(at(1))),
            ),
        )


@pytest.mark.unit
def test_assignment_allocation_and_delegation_are_explicit() -> None:
    with pytest.raises(ValueError, match="between 1 and 100"):
        PositionAssignment(
            id=UUID("019914b2-1a40-7000-8000-000000000064"),
            person_id=ALICE,
            position_id=UUID("019914b2-1a40-7000-8000-000000000051"),
            scope_unit_id=CVSI,
            kind=AssignmentKind.SECONDARY,
            validity=DateRange(at(1)),
            allocation_percent=101,
        )
    with pytest.raises(ValueError, match="delegating principal"):
        PositionAssignment(
            id=UUID("019914b2-1a40-7000-8000-000000000065"),
            person_id=ALICE,
            position_id=UUID("019914b2-1a40-7000-8000-000000000051"),
            scope_unit_id=CVSI,
            kind=AssignmentKind.DELEGATION,
            validity=DateRange(at(1)),
        )
