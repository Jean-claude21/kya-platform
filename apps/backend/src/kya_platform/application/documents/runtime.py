"""Deterministic validation and workflow planning for native KYA documents."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast
from uuid import UUID, uuid7

from kya_platform.contracts.artifact_manifest import CapabilityPermission
from kya_platform.contracts.document_type import (
    ActorSelector,
    ConditionClause,
    ConditionOperator,
    DocumentTypeDefinition,
    ReferenceBinding,
    ReferenceConsistency,
    WorkflowTransition,
)
from kya_platform.contracts.record_schema import RecordField, RecordFieldType
from kya_platform.domain.documents import (
    DocumentEvidence,
    DocumentRevision,
    DocumentValue,
    EvidenceKind,
    canonical_digest,
)


class DocumentValidationError(ValueError):
    """Submitted data does not satisfy the published document definition."""


class ReferenceResolutionError(DocumentValidationError):
    """A governed relation could not be resolved without leaking inaccessible data."""


class TransitionDeniedError(PermissionError):
    """The requested workflow transition is absent or unauthorized."""


_SHA256 = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class ReferenceResolutionRequest:
    binding: ReferenceBinding
    reference_id: str
    actor_id: UUID
    owner_scope: str


@dataclass(frozen=True, slots=True)
class ResolvedReference:
    reference_id: str
    snapshot: Mapping[str, DocumentValue]


class ReferenceResolver(Protocol):
    async def resolve(self, request: ReferenceResolutionRequest) -> ResolvedReference | None:
        """Resolve only after checking the binding's required permission."""


@dataclass(frozen=True, slots=True)
class TransitionAuthorizationRequest:
    actor_id: UUID
    owner_scope: str
    record_id: UUID
    permission: CapabilityPermission
    actors: tuple[ActorSelector, ...]
    payload: Mapping[str, DocumentValue]


class TransitionAuthorizer(Protocol):
    async def authorize(self, request: TransitionAuthorizationRequest) -> bool: ...


@dataclass(frozen=True, slots=True)
class NotificationIntent:
    policy_key: str
    event: str
    recipients: tuple[ActorSelector, ...]
    channels: tuple[str, ...]
    template: str
    available_at: datetime


@dataclass(frozen=True, slots=True)
class TransitionPlan:
    transition_key: str
    from_state: str
    to_state: str
    revision: DocumentRevision
    evidence: DocumentEvidence
    notifications: tuple[NotificationIntent, ...]


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_valid_byte_size(value: object, *, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value <= maximum


def _is_decimal(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return False
    try:
        Decimal(str(value))
    except InvalidOperation:
        return False
    return True


def _is_iso_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_iso_datetime(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _reference_ids(value: object, *, multiple: bool) -> tuple[str, ...] | None:
    if multiple:
        if not isinstance(value, Sequence) or isinstance(value, str | bytes):
            return None
        values = value
    else:
        if not isinstance(value, str):
            return None
        values = (value,)
    identifiers: list[str] = []
    for item in values:
        if not isinstance(item, str) or not item.strip() or len(item) > 255:
            return None
        identifiers.append(item)
    return tuple(identifiers)


def _is_attachment(field: RecordField, value: object) -> bool:
    policy = field.attachment
    if policy is None or not isinstance(value, Mapping):
        return False
    digest = value.get("digest")
    object_key = value.get("objectKey")
    media_type = value.get("mediaType")
    byte_size = value.get("byteSize")
    return (
        isinstance(digest, str)
        and _SHA256.fullmatch(digest) is not None
        and isinstance(object_key, str)
        and bool(object_key.strip())
        and isinstance(media_type, str)
        and media_type in policy.allowed_media_types
        and _is_valid_byte_size(byte_size, maximum=policy.max_bytes_per_file)
    )


def _valid_field_value(field: RecordField, value: object) -> bool:
    if value is None:
        return not field.required
    if field.multiple:
        if not isinstance(value, Sequence) or isinstance(value, str | bytes):
            return False
        return all(
            _valid_field_value(field.model_copy(update={"multiple": False}), item) for item in value
        )
    validators: dict[RecordFieldType, Callable[[object], bool]] = {
        RecordFieldType.TEXT: lambda candidate: (
            isinstance(candidate, str) and (not field.required or bool(candidate.strip()))
        ),
        RecordFieldType.LONG_TEXT: lambda candidate: (
            isinstance(candidate, str) and (not field.required or bool(candidate.strip()))
        ),
        RecordFieldType.INTEGER: _is_integer,
        RecordFieldType.DECIMAL: _is_decimal,
        RecordFieldType.BOOLEAN: lambda candidate: isinstance(candidate, bool),
        RecordFieldType.DATE: _is_iso_date,
        RecordFieldType.DATETIME: _is_iso_datetime,
        RecordFieldType.CHOICE: lambda candidate: (
            isinstance(candidate, str) and candidate in field.choices
        ),
        RecordFieldType.RELATION: lambda candidate: (
            isinstance(candidate, str) and bool(candidate.strip())
        ),
        RecordFieldType.ATTACHMENT: lambda candidate: _is_attachment(field, candidate),
        RecordFieldType.JSON: lambda _candidate: True,
    }
    return validators[field.field_type](value)


def validate_payload(
    definition: DocumentTypeDefinition, payload: Mapping[str, DocumentValue]
) -> None:
    """Reject undeclared, missing or incorrectly typed form data."""

    fields = {field.key: field for field in definition.record_schema.fields}
    unknown = set(payload) - set(fields)
    if unknown:
        raise DocumentValidationError(f"undeclared fields: {', '.join(sorted(unknown))}")
    missing = {
        field.key for field in fields.values() if field.required and field.key not in payload
    }
    if missing:
        raise DocumentValidationError(f"required fields missing: {', '.join(sorted(missing))}")
    invalid = [key for key, value in payload.items() if not _valid_field_value(fields[key], value)]
    if invalid:
        raise DocumentValidationError(f"invalid field values: {', '.join(sorted(invalid))}")


async def resolve_references(
    definition: DocumentTypeDefinition,
    payload: Mapping[str, DocumentValue],
    *,
    resolver: ReferenceResolver,
    actor_id: UUID,
    owner_scope: str,
) -> dict[str, DocumentValue]:
    """Replace submitted identifiers with governed references and approved snapshots."""

    validate_payload(definition, payload)
    resolved_payload = dict(payload)
    fields = {field.key: field for field in definition.record_schema.fields}
    for binding in definition.references:
        if binding.field not in payload or payload[binding.field] is None:
            continue
        identifiers = _reference_ids(
            payload[binding.field], multiple=fields[binding.field].multiple
        )
        if identifiers is None:
            raise ReferenceResolutionError(f"invalid reference value for {binding.field}")
        values: list[DocumentValue] = []
        for identifier in identifiers:
            resolved = await resolver.resolve(
                ReferenceResolutionRequest(
                    binding=binding,
                    reference_id=identifier,
                    actor_id=actor_id,
                    owner_scope=owner_scope,
                )
            )
            if resolved is None or resolved.reference_id != identifier:
                raise ReferenceResolutionError(
                    f"reference unavailable or unauthorized for {binding.field}"
                )
            allowed_snapshot = {
                key: value
                for key, value in resolved.snapshot.items()
                if key in binding.snapshot_fields
            }
            if binding.consistency is not ReferenceConsistency.LIVE and set(
                allowed_snapshot
            ) != set(binding.snapshot_fields):
                raise ReferenceResolutionError(f"incomplete reference snapshot for {binding.field}")
            reference: dict[str, DocumentValue] = {
                "id": identifier,
                "providerArtifactId": binding.provider_artifact_id,
                "resourceType": binding.resource_type,
            }
            if binding.consistency is not ReferenceConsistency.LIVE:
                reference["snapshot"] = allowed_snapshot
            values.append(reference)
        resolved_payload[binding.field] = values if fields[binding.field].multiple else values[0]
    return resolved_payload


def _condition_matches(condition: ConditionClause, payload: Mapping[str, DocumentValue]) -> bool:
    actual = payload.get(condition.field)
    if isinstance(actual, Mapping) and isinstance(actual.get("id"), str):
        actual = actual["id"]
    expected = condition.value
    if condition.operator is ConditionOperator.IS_SET:
        return actual is not None and actual != "" and actual != () and actual != []
    if condition.operator is ConditionOperator.EQUALS:
        return actual == expected
    if condition.operator is ConditionOperator.NOT_EQUALS:
        return actual != expected
    if condition.operator is ConditionOperator.IN:
        return actual in cast(tuple[DocumentValue, ...], expected)
    if condition.operator is ConditionOperator.NOT_IN:
        return actual not in cast(tuple[DocumentValue, ...], expected)
    if not isinstance(actual, int | float) or isinstance(actual, bool):
        return False
    if not isinstance(expected, int | float) or isinstance(expected, bool):
        return False
    if condition.operator is ConditionOperator.GREATER_THAN:
        return actual > expected
    if condition.operator is ConditionOperator.GREATER_THAN_OR_EQUAL:
        return actual >= expected
    if condition.operator is ConditionOperator.LESS_THAN:
        return actual < expected
    return actual <= expected


def _transition(
    definition: DocumentTypeDefinition, transition_key: str, current_state: str
) -> WorkflowTransition:
    transition = next(
        (item for item in definition.workflow.transitions if item.key == transition_key), None
    )
    if transition is None or transition.from_state != current_state:
        raise TransitionDeniedError("transition is unavailable from the current state")
    return transition


async def plan_transition(
    definition: DocumentTypeDefinition,
    *,
    record_id: UUID,
    current_state: str,
    current_revision: int,
    payload: Mapping[str, DocumentValue],
    transition_key: str,
    actor_id: UUID,
    owner_scope: str,
    occurred_at: datetime,
    correlation_id: UUID,
    authorizer: TransitionAuthorizer,
) -> TransitionPlan:
    """Validate and authorize one transition without producing side effects."""

    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise DocumentValidationError("transition time must include a timezone")
    transition = _transition(definition, transition_key, current_state)
    if not all(_condition_matches(condition, payload) for condition in transition.conditions):
        raise TransitionDeniedError("transition conditions are not satisfied")
    allowed = await authorizer.authorize(
        TransitionAuthorizationRequest(
            actor_id=actor_id,
            owner_scope=owner_scope,
            record_id=record_id,
            permission=transition.permission,
            actors=transition.actors,
            payload=payload,
        )
    )
    if not allowed:
        raise TransitionDeniedError("actor is not authorized for this transition")
    next_revision = current_revision + 1
    revision = DocumentRevision(
        record_id=record_id,
        revision=next_revision,
        payload=payload,
        digest=canonical_digest(payload),
        authored_by=actor_id,
        created_at=occurred_at,
    )
    evidence_payload: dict[str, DocumentValue] = {
        "transitionKey": transition.key,
        "fromState": transition.from_state,
        "toState": transition.to_state,
        "correlationId": str(correlation_id),
        "revisionDigest": revision.digest,
    }
    evidence = DocumentEvidence(
        id=uuid7(),
        record_id=record_id,
        revision=next_revision,
        kind=EvidenceKind.TRANSITION,
        actor_id=actor_id,
        evidence=evidence_payload,
        digest=canonical_digest(evidence_payload),
        occurred_at=occurred_at,
    )
    event = f"document.{transition.to_state}"
    notifications = tuple(
        NotificationIntent(
            policy_key=policy.key,
            event=policy.event,
            recipients=policy.recipients,
            channels=tuple(channel.value for channel in policy.channels),
            template=policy.template,
            available_at=occurred_at + timedelta(minutes=policy.delay_minutes),
        )
        for policy in definition.notifications
        if policy.event == event
    )
    return TransitionPlan(
        transition_key=transition.key,
        from_state=transition.from_state,
        to_state=transition.to_state,
        revision=revision,
        evidence=evidence,
        notifications=notifications,
    )


__all__ = [
    "DocumentValidationError",
    "NotificationIntent",
    "ReferenceResolutionError",
    "ReferenceResolutionRequest",
    "ReferenceResolver",
    "ResolvedReference",
    "TransitionAuthorizationRequest",
    "TransitionAuthorizer",
    "TransitionDeniedError",
    "TransitionPlan",
    "plan_transition",
    "resolve_references",
    "validate_payload",
]
