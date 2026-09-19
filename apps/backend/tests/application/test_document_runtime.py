"""Native document runtime validates forms, references and transitions deterministically."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from kya_platform.application.documents.runtime import (
    DocumentValidationError,
    ReferenceResolutionError,
    ReferenceResolutionRequest,
    ResolvedReference,
    TransitionAuthorizationRequest,
    TransitionDeniedError,
    _condition_matches,
    plan_transition,
    resolve_references,
    validate_payload,
)
from kya_platform.contracts.document_type import ConditionClause, DocumentTypeDefinition

RECORD_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_ID = UUID("22222222-2222-4222-8222-222222222222")
CORRELATION_ID = UUID("33333333-3333-4333-8333-333333333333")
NOW = datetime(2026, 9, 19, 11, tzinfo=UTC)


def definition() -> DocumentTypeDefinition:
    return DocumentTypeDefinition.model_validate(
        {
            "schemaVersion": "1",
            "id": "kya:document-type:mission-request",
            "version": "0.1.0",
            "name": "Mission request",
            "recordSchema": {
                "schemaVersion": "1",
                "id": "kya:data-schema:mission-request",
                "version": "0.1.0",
                "name": "Mission request",
                "ownerScope": "workspace:operations",
                "fields": [
                    {
                        "key": "requester",
                        "label": "Requester",
                        "type": "relation",
                        "required": True,
                        "relation": {
                            "targetSchemaId": "kya:data-schema:person",
                            "cardinality": "many-to-one",
                        },
                    },
                    {
                        "key": "client",
                        "label": "Client",
                        "type": "relation",
                        "required": True,
                        "relation": {
                            "targetSchemaId": "kya:data-schema:client",
                            "cardinality": "many-to-one",
                        },
                    },
                    {"key": "purpose", "label": "Purpose", "type": "long-text", "required": True},
                    {"key": "start_at", "label": "Start", "type": "datetime", "required": True},
                    {"key": "estimated_cost", "label": "Cost", "type": "decimal"},
                    {"key": "duration_days", "label": "Duration", "type": "integer"},
                    {"key": "requires_vehicle", "label": "Vehicle", "type": "boolean"},
                    {"key": "return_date", "label": "Return date", "type": "date"},
                    {
                        "key": "priority",
                        "label": "Priority",
                        "type": "choice",
                        "choices": ["normal", "urgent"],
                    },
                    {
                        "key": "tags",
                        "label": "Tags",
                        "type": "text",
                        "multiple": True,
                    },
                    {"key": "metadata", "label": "Metadata", "type": "json"},
                    {
                        "key": "supporting_document",
                        "label": "Supporting document",
                        "type": "attachment",
                        "attachment": {
                            "maxFiles": 1,
                            "maxBytesPerFile": 1048576,
                            "allowedMediaTypes": ["application/pdf"],
                        },
                    },
                ],
                "access": {
                    "enforcement": "record",
                    "permissions": ["view", "create", "administer"],
                },
                "retention": {"retainDays": 1825, "softDeleteDays": 30},
            },
            "references": [
                {
                    "field": "requester",
                    "providerArtifactId": "kya:api:kya-core",
                    "resourceType": "person",
                    "valueField": "id",
                    "displayFields": ["display_name"],
                    "searchFields": ["display_name", "employee_number"],
                    "snapshotFields": ["display_name", "employee_number"],
                    "consistency": "live-with-snapshot",
                    "requiredPermission": "person.reference",
                },
                {
                    "field": "client",
                    "providerArtifactId": "kya:api:kya-core",
                    "resourceType": "client",
                    "valueField": "id",
                    "displayFields": ["name"],
                    "searchFields": ["name", "account_number"],
                    "snapshotFields": ["name", "account_number"],
                    "consistency": "live-with-snapshot",
                    "requiredPermission": "client.reference",
                },
            ],
            "workflow": {
                "initialState": "draft",
                "states": [
                    {"key": "draft", "name": "Draft", "category": "draft"},
                    {"key": "submitted", "name": "Submitted", "category": "active"},
                    {
                        "key": "approved",
                        "name": "Approved",
                        "category": "completed",
                        "terminal": True,
                    },
                ],
                "transitions": [
                    {
                        "key": "submit",
                        "name": "Submit",
                        "fromState": "draft",
                        "toState": "submitted",
                        "permission": "create",
                        "actors": [{"kind": "actor", "value": "current"}],
                        "conditions": [{"field": "purpose", "operator": "is-set"}],
                    },
                    {
                        "key": "approve",
                        "name": "Approve",
                        "fromState": "submitted",
                        "toState": "approved",
                        "permission": "administer",
                        "actors": [{"kind": "role", "value": "operations-manager"}],
                    },
                ],
            },
            "notifications": [
                {
                    "key": "mission_submitted",
                    "event": "document.submitted",
                    "recipients": [{"kind": "role", "value": "operations-manager"}],
                    "channels": ["in-app", "email"],
                    "template": "operations.mission.submitted",
                    "delayMinutes": 5,
                }
            ],
            "views": [
                {
                    "key": "mission_form",
                    "name": "Mission form",
                    "type": "form",
                    "fields": ["requester", "client", "purpose", "start_at", "estimated_cost"],
                    "titleField": "purpose",
                    "default": True,
                }
            ],
        }
    )


def payload() -> dict[str, object]:
    return {
        "requester": "person-42",
        "client": "client-7",
        "purpose": "Inspect the solar installation",
        "start_at": "2026-09-22T08:00:00Z",
        "estimated_cost": "125000.50",
    }


class Resolver:
    def __init__(self, *, denied: str | None = None, incomplete: str | None = None) -> None:
        self.denied = denied
        self.incomplete = incomplete
        self.requests: list[ReferenceResolutionRequest] = []

    async def resolve(self, request: ReferenceResolutionRequest) -> ResolvedReference | None:
        self.requests.append(request)
        if request.reference_id == self.denied:
            return None
        if request.binding.resource_type == "person":
            snapshot = {"display_name": "Afi Mensah", "employee_number": "EMP-42"}
        else:
            snapshot = {"name": "Solar Client", "account_number": "CLI-7"}
        if request.reference_id == self.incomplete:
            snapshot.pop(next(iter(snapshot)))
        return ResolvedReference(request.reference_id, snapshot)


class Authorizer:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.requests: list[TransitionAuthorizationRequest] = []

    async def authorize(self, request: TransitionAuthorizationRequest) -> bool:
        self.requests.append(request)
        return self.allowed


def test_payload_validation_rejects_unknown_missing_and_wrong_types() -> None:
    valid = payload()
    validate_payload(definition(), valid)  # type: ignore[arg-type]

    with pytest.raises(DocumentValidationError, match="undeclared"):
        validate_payload(definition(), {**valid, "hidden_admin": True})  # type: ignore[arg-type]
    with pytest.raises(DocumentValidationError, match="required"):
        validate_payload(
            definition(), {key: value for key, value in valid.items() if key != "client"}
        )  # type: ignore[arg-type]
    with pytest.raises(DocumentValidationError, match="invalid"):
        validate_payload(definition(), {**valid, "start_at": "tomorrow"})  # type: ignore[arg-type]


def test_payload_validation_enforces_attachment_integrity_metadata() -> None:
    valid_attachment = {
        "digest": "a" * 64,
        "objectKey": "documents/mission-request/quote.pdf",
        "mediaType": "application/pdf",
        "byteSize": 2048,
    }
    validate_payload(
        definition(),
        {**payload(), "supporting_document": valid_attachment},  # type: ignore[arg-type]
    )

    for invalid_attachment in (
        {**valid_attachment, "digest": "not-a-digest"},
        {**valid_attachment, "mediaType": "application/octet-stream"},
        {**valid_attachment, "byteSize": 1048577},
        {**valid_attachment, "objectKey": ""},
    ):
        with pytest.raises(DocumentValidationError, match="invalid"):
            validate_payload(
                definition(),
                {**payload(), "supporting_document": invalid_attachment},  # type: ignore[arg-type]
            )


def test_payload_validation_supports_all_form_value_shapes() -> None:
    complete = {
        **payload(),
        "duration_days": 3,
        "requires_vehicle": True,
        "return_date": "2026-09-25",
        "priority": "urgent",
        "tags": ["solar", "inspection"],
        "metadata": {"source": "field-team"},
    }
    validate_payload(definition(), complete)  # type: ignore[arg-type]
    validate_payload(definition(), {**complete, "estimated_cost": 2500.5})  # type: ignore[arg-type]
    validate_payload(definition(), {**complete, "return_date": None})  # type: ignore[arg-type]

    invalid_values = {
        "purpose": "   ",
        "estimated_cost": "not-a-number",
        "duration_days": True,
        "requires_vehicle": "yes",
        "return_date": "next-week",
        "start_at": "2026-09-22T08:00:00",
        "priority": "critical",
        "tags": "solar",
    }
    for field, value in invalid_values.items():
        with pytest.raises(DocumentValidationError, match="invalid"):
            validate_payload(definition(), {**complete, field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("operator", "expected", "actual", "matches"),
    [
        ("equals", "client-7", {"id": "client-7"}, True),
        ("not-equals", "client-8", "client-7", True),
        ("in", ("normal", "urgent"), "urgent", True),
        ("not-in", ("cancelled",), "urgent", True),
        ("greater-than", 4, 5, True),
        ("greater-than-or-equal", 5, 5, True),
        ("less-than", 6, 5, True),
        ("less-than-or-equal", 5, 5, True),
        ("greater-than", 4, "five", False),
        ("greater-than", "four", 5, False),
    ],
)
def test_workflow_conditions_cover_scalar_reference_and_numeric_values(
    operator: str, expected: object, actual: object, matches: bool
) -> None:
    condition = ConditionClause.model_validate(
        {"field": "value", "operator": operator, "value": expected}
    )
    assert _condition_matches(condition, {"value": actual}) is matches  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_references_are_authorized_and_snapshotted_from_source_of_truth() -> None:
    resolver = Resolver()
    resolved = await resolve_references(
        definition(),
        payload(),  # type: ignore[arg-type]
        resolver=resolver,
        actor_id=ACTOR_ID,
        owner_scope="workspace:operations",
    )

    assert resolved["requester"] == {
        "id": "person-42",
        "providerArtifactId": "kya:api:kya-core",
        "resourceType": "person",
        "snapshot": {"display_name": "Afi Mensah", "employee_number": "EMP-42"},
    }
    assert resolved["client"] == {
        "id": "client-7",
        "providerArtifactId": "kya:api:kya-core",
        "resourceType": "client",
        "snapshot": {"name": "Solar Client", "account_number": "CLI-7"},
    }
    assert {request.binding.required_permission for request in resolver.requests} == {
        "person.reference",
        "client.reference",
    }


@pytest.mark.asyncio
async def test_reference_resolution_fails_closed() -> None:
    with pytest.raises(ReferenceResolutionError, match="unauthorized"):
        await resolve_references(
            definition(),
            payload(),  # type: ignore[arg-type]
            resolver=Resolver(denied="client-7"),
            actor_id=ACTOR_ID,
            owner_scope="workspace:operations",
        )
    with pytest.raises(ReferenceResolutionError, match="incomplete"):
        await resolve_references(
            definition(),
            payload(),  # type: ignore[arg-type]
            resolver=Resolver(incomplete="person-42"),
            actor_id=ACTOR_ID,
            owner_scope="workspace:operations",
        )


@pytest.mark.asyncio
async def test_transition_plan_binds_revision_evidence_authorization_and_notifications() -> None:
    authorizer = Authorizer()
    plan = await plan_transition(
        definition(),
        record_id=RECORD_ID,
        current_state="draft",
        current_revision=1,
        payload=payload(),  # type: ignore[arg-type]
        transition_key="submit",
        actor_id=ACTOR_ID,
        owner_scope="workspace:operations",
        occurred_at=NOW,
        correlation_id=CORRELATION_ID,
        authorizer=authorizer,
    )

    assert plan.from_state == "draft"
    assert plan.to_state == "submitted"
    assert plan.revision.revision == plan.evidence.revision == 2
    assert plan.evidence.evidence["revisionDigest"] == plan.revision.digest
    assert plan.notifications[0].available_at.isoformat() == "2026-09-19T11:05:00+00:00"
    assert authorizer.requests[0].permission.value == "create"


@pytest.mark.asyncio
async def test_transition_fails_closed_for_state_condition_or_permission() -> None:
    arguments = {
        "definition": definition(),
        "record_id": RECORD_ID,
        "current_state": "draft",
        "current_revision": 1,
        "payload": payload(),
        "transition_key": "submit",
        "actor_id": ACTOR_ID,
        "owner_scope": "workspace:operations",
        "occurred_at": NOW,
        "correlation_id": CORRELATION_ID,
    }
    with pytest.raises(TransitionDeniedError, match="current state"):
        await plan_transition(
            **{**arguments, "current_state": "submitted"}, authorizer=Authorizer()
        )  # type: ignore[arg-type]
    without_purpose = {**payload(), "purpose": ""}
    with pytest.raises(TransitionDeniedError, match="conditions"):
        await plan_transition(**{**arguments, "payload": without_purpose}, authorizer=Authorizer())  # type: ignore[arg-type]
    with pytest.raises(TransitionDeniedError, match="not authorized"):
        await plan_transition(**arguments, authorizer=Authorizer(False))  # type: ignore[arg-type]
    with pytest.raises(DocumentValidationError, match="timezone"):
        await plan_transition(
            **{**arguments, "occurred_at": datetime(2026, 9, 19, 11)},
            authorizer=Authorizer(),
        )  # type: ignore[arg-type]
