"""Temporal organization model for KYA-Energy Group."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

_KEY = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")


@dataclass(frozen=True, slots=True)
class DateRange:
    """Half-open validity period: start included, end excluded."""

    valid_from: datetime
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        _require_aware(self.valid_from, "valid_from")
        if self.valid_until is None:
            return
        _require_aware(self.valid_until, "valid_until")
        if self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")

    def contains(self, instant: datetime) -> bool:
        _require_aware(instant, "instant")
        return self.valid_from <= instant and (
            self.valid_until is None or instant < self.valid_until
        )


@dataclass(frozen=True, slots=True)
class OrganizationalUnitType:
    key: str
    label: str
    allowed_parent_types: frozenset[str] = field(default_factory=frozenset)
    is_temporary: bool = False

    def __post_init__(self) -> None:
        if _KEY.fullmatch(self.key) is None:
            raise ValueError("unit type key must be a stable kebab-case identifier")
        if not self.label.strip():
            raise ValueError("unit type label is required")
        if any(_KEY.fullmatch(key) is None for key in self.allowed_parent_types):
            raise ValueError("allowed parent type keys must be stable identifiers")

    def accepts_parent(self, parent_type: str) -> bool:
        return parent_type in self.allowed_parent_types


@dataclass(frozen=True, slots=True)
class OrganizationalUnit:
    id: UUID
    key: str
    type_key: str
    name: str
    validity: DateRange

    def __post_init__(self) -> None:
        if _KEY.fullmatch(self.key) is None:
            raise ValueError("unit key must be a stable kebab-case identifier")
        if _KEY.fullmatch(self.type_key) is None:
            raise ValueError("unit type key must be a stable identifier")
        if not self.name.strip():
            raise ValueError("unit name is required")


class RelationKind(StrEnum):
    HIERARCHICAL = "hierarchical"
    TRANSVERSAL = "transversal"


@dataclass(frozen=True, slots=True)
class OrganizationalUnitRelation:
    parent_unit_id: UUID
    child_unit_id: UUID
    kind: RelationKind
    validity: DateRange

    def __post_init__(self) -> None:
        if self.parent_unit_id == self.child_unit_id:
            raise ValueError("an organizational unit cannot relate to itself")


@dataclass(frozen=True, slots=True)
class OrganizationGraph:
    units: tuple[OrganizationalUnit, ...]
    relations: tuple[OrganizationalUnitRelation, ...] = ()

    def __post_init__(self) -> None:
        unit_ids = [unit.id for unit in self.units]
        if len(unit_ids) != len(set(unit_ids)):
            raise ValueError("organizational unit ids must be unique")
        known = set(unit_ids)
        for relation in self.relations:
            if relation.parent_unit_id not in known or relation.child_unit_id not in known:
                raise ValueError("organizational relation references an unknown unit")
        for instant in {relation.validity.valid_from for relation in self.relations}:
            if self._has_hierarchical_cycle(instant):
                raise ValueError("hierarchical organizational relations contain a cycle")

    def _has_hierarchical_cycle(self, instant: datetime) -> bool:
        children: dict[UUID, set[UUID]] = {}
        for relation in self.relations:
            if relation.kind is RelationKind.HIERARCHICAL and relation.validity.contains(instant):
                children.setdefault(relation.parent_unit_id, set()).add(relation.child_unit_id)

        visiting: set[UUID] = set()
        visited: set[UUID] = set()

        def visit(unit_id: UUID) -> bool:
            if unit_id in visiting:
                return True
            if unit_id in visited:
                return False
            visiting.add(unit_id)
            if any(visit(child_id) for child_id in children.get(unit_id, ())):
                return True
            visiting.remove(unit_id)
            visited.add(unit_id)
            return False

        return any(visit(unit_id) for unit_id in (unit.id for unit in self.units))

    def with_relation(self, relation: OrganizationalUnitRelation) -> OrganizationGraph:
        return OrganizationGraph(self.units, (*self.relations, relation))

    def parent_ids(self, child_unit_id: UUID, instant: datetime) -> tuple[UUID, ...]:
        return tuple(
            relation.parent_unit_id
            for relation in self.relations
            if relation.child_unit_id == child_unit_id
            and relation.kind is RelationKind.HIERARCHICAL
            and relation.validity.contains(instant)
        )


@dataclass(frozen=True, slots=True)
class Position:
    id: UUID
    key: str
    name: str
    unit_id: UUID
    validity: DateRange

    def __post_init__(self) -> None:
        if _KEY.fullmatch(self.key) is None:
            raise ValueError("position key must be a stable kebab-case identifier")
        if not self.name.strip():
            raise ValueError("position name is required")


class AssignmentKind(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    ACTING = "acting"
    DELEGATION = "delegation"


@dataclass(frozen=True, slots=True)
class PositionAssignment:
    id: UUID
    principal_id: UUID
    position_id: UUID
    scope_unit_id: UUID
    kind: AssignmentKind
    validity: DateRange
    allocation_percent: int | None = None
    reports_to_assignment_id: UUID | None = None
    delegated_by: UUID | None = None

    def __post_init__(self) -> None:
        if self.allocation_percent is not None and not 1 <= self.allocation_percent <= 100:
            raise ValueError("allocation_percent must be between 1 and 100")
        if self.kind is AssignmentKind.DELEGATION and self.delegated_by is None:
            raise ValueError("a delegation must identify its delegating principal")

    def is_active(self, instant: datetime) -> bool:
        return self.validity.contains(instant)


__all__ = [
    "AssignmentKind",
    "DateRange",
    "OrganizationGraph",
    "OrganizationalUnit",
    "OrganizationalUnitRelation",
    "OrganizationalUnitType",
    "Position",
    "PositionAssignment",
    "RelationKind",
]
