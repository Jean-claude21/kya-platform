"""Contract tests for portable KYA document type definitions."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from kya_platform.contracts.document_type import (
    ConditionClause,
    DocumentTypeDefinition,
    ReferenceBinding,
)
from kya_platform.contracts.export import export_contracts


def document_type_payload() -> dict[str, object]:
    return {
        "schemaVersion": "1",
        "id": "kya:document-type:employee-satisfaction",
        "version": "0.1.0",
        "name": "Employee satisfaction",
        "recordSchema": {
            "schemaVersion": "1",
            "id": "kya:data-schema:employee-satisfaction-response",
            "version": "0.1.0",
            "name": "Employee satisfaction response",
            "ownerScope": "workspace:people",
            "fields": [
                {
                    "key": "employee",
                    "label": "Employee",
                    "type": "relation",
                    "required": True,
                    "relation": {
                        "targetSchemaId": "kya:data-schema:employee",
                        "cardinality": "many-to-one",
                    },
                },
                {"key": "department", "label": "Department", "type": "text"},
                {"key": "rating", "label": "Rating", "type": "integer"},
                {"key": "submitted_at", "label": "Submitted at", "type": "datetime"},
            ],
            "access": {
                "enforcement": "record",
                "permissions": ["view", "create", "edit", "administer"],
            },
            "retention": {
                "retainDays": 1825,
                "softDeleteDays": 30,
                "legalHoldSupported": True,
            },
        },
        "references": [
            {
                "field": "employee",
                "providerArtifactId": "kya:api:people-directory",
                "resourceType": "employee",
                "valueField": "id",
                "displayFields": ["display_name", "employee_number"],
                "searchFields": ["display_name", "employee_number"],
                "snapshotFields": ["display_name", "department"],
                "consistency": "live-with-snapshot",
                "requiredPermission": "employee.reference",
            }
        ],
        "privacy": {
            "identityMode": "anonymous",
            "separateIdentityStore": True,
            "minimumAggregateSize": 10,
            "allowIndividualReporting": False,
            "sensitiveFields": ["employee"],
        },
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
                },
                {
                    "key": "approve",
                    "name": "Approve",
                    "fromState": "submitted",
                    "toState": "approved",
                    "permission": "administer",
                    "actors": [{"kind": "role", "value": "people-manager"}],
                    "conditions": [{"field": "rating", "operator": "is-set"}],
                },
            ],
        },
        "signatures": [
            {
                "key": "people_approval",
                "transitionKey": "approve",
                "mode": "internal-approval",
                "signers": [{"kind": "role", "value": "people-manager"}],
                "minimumSignatures": 1,
            }
        ],
        "notifications": [
            {
                "key": "response_submitted",
                "event": "document.submitted",
                "recipients": [{"kind": "role", "value": "people-manager"}],
                "channels": ["in-app", "email"],
                "template": "people.satisfaction.response-submitted",
            }
        ],
        "views": [
            {
                "key": "response_form",
                "name": "Response form",
                "type": "form",
                "fields": ["employee", "department", "rating"],
                "titleField": "employee",
                "default": True,
            },
            {
                "key": "response_table",
                "name": "Responses",
                "type": "table",
                "fields": ["department", "rating", "submitted_at"],
            },
        ],
        "metrics": [
            {
                "key": "response_count",
                "name": "Response count",
                "aggregation": "count",
                "groupBy": ["department"],
            },
            {
                "key": "average_rating",
                "name": "Average rating",
                "aggregation": "average",
                "field": "rating",
                "groupBy": ["department"],
            },
        ],
    }


@pytest.mark.contract
def test_accepts_a_complete_document_type() -> None:
    definition = DocumentTypeDefinition.model_validate(document_type_payload())

    assert definition.document_type_id == "kya:document-type:employee-satisfaction"
    assert definition.workflow.initial_state == "draft"
    assert definition.views[0].default is True
    assert definition.metrics[1].field == "rating"


@pytest.mark.contract
def test_rejects_workflow_transition_to_unknown_state() -> None:
    payload = document_type_payload()
    workflow = payload["workflow"]
    assert isinstance(workflow, dict)
    transitions = workflow["transitions"]
    assert isinstance(transitions, list)
    transitions[0]["toState"] = "missing"

    with pytest.raises(ValidationError, match="declared states"):
        DocumentTypeDefinition.model_validate(payload)


@pytest.mark.contract
def test_rejects_view_field_not_declared_in_record_schema() -> None:
    payload = document_type_payload()
    views = payload["views"]
    assert isinstance(views, list)
    views[0]["fields"].append("secret_salary")

    with pytest.raises(ValidationError, match="views must reference"):
        DocumentTypeDefinition.model_validate(payload)


@pytest.mark.contract
def test_rejects_signature_for_unknown_transition() -> None:
    payload = document_type_payload()
    signatures = payload["signatures"]
    assert isinstance(signatures, list)
    signatures[0]["transitionKey"] = "missing"

    with pytest.raises(ValidationError, match="declared transitions"):
        DocumentTypeDefinition.model_validate(payload)


@pytest.mark.contract
def test_rejects_unsafe_anonymous_reporting() -> None:
    payload = document_type_payload()
    privacy = payload["privacy"]
    assert isinstance(privacy, dict)
    privacy["allowIndividualReporting"] = True

    with pytest.raises(ValidationError, match="cannot allow individual reporting"):
        DocumentTypeDefinition.model_validate(payload)


@pytest.mark.contract
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {"consistency": "live", "snapshotFields": ["display_name"]},
            "live references cannot declare snapshot fields",
        ),
        (
            {"consistency": "snapshot", "snapshotFields": []},
            "snapshot references require snapshot fields",
        ),
    ],
)
def test_rejects_inconsistent_reference_snapshot_policy(
    changes: dict[str, object], message: str
) -> None:
    reference = {
        "field": "employee",
        "providerArtifactId": "kya:api:people-directory",
        "resourceType": "employee",
        "valueField": "id",
        "displayFields": ["display_name"],
        "snapshotFields": ["display_name"],
        "requiredPermission": "employee.reference",
        **changes,
    }

    with pytest.raises(ValidationError, match=message):
        ReferenceBinding.model_validate(reference)


@pytest.mark.contract
def test_rejects_empty_membership_condition() -> None:
    with pytest.raises(ValidationError, match="non-empty value list"):
        ConditionClause.model_validate({"field": "department", "operator": "in", "value": []})


@pytest.mark.contract
def test_rejects_terminal_initial_workflow_state() -> None:
    payload = document_type_payload()
    workflow = payload["workflow"]
    assert isinstance(workflow, dict)
    workflow["initialState"] = "approved"

    with pytest.raises(ValidationError, match="initial state cannot be terminal"):
        DocumentTypeDefinition.model_validate(payload)


@pytest.mark.contract
def test_rejects_calendar_view_without_date_field() -> None:
    payload = document_type_payload()
    views = payload["views"]
    assert isinstance(views, list)
    views[0]["type"] = "calendar"

    with pytest.raises(ValidationError, match="calendar views require a date field"):
        DocumentTypeDefinition.model_validate(payload)


@pytest.mark.contract
def test_rejects_numeric_metric_on_text_field() -> None:
    payload = document_type_payload()
    metrics = payload["metrics"]
    assert isinstance(metrics, list)
    metrics[1]["field"] = "department"

    with pytest.raises(ValidationError, match="numeric record fields"):
        DocumentTypeDefinition.model_validate(payload)


@pytest.mark.contract
def test_rejects_anonymous_aggregation_below_three() -> None:
    payload = document_type_payload()
    privacy = payload["privacy"]
    assert isinstance(privacy, dict)
    privacy["minimumAggregateSize"] = 2

    with pytest.raises(ValidationError, match="threshold of three"):
        DocumentTypeDefinition.model_validate(payload)


@pytest.mark.contract
def test_rejects_duplicate_notification_channels() -> None:
    payload = document_type_payload()
    notifications = payload["notifications"]
    assert isinstance(notifications, list)
    notifications[0]["channels"] = ["email", "email"]

    with pytest.raises(ValidationError, match="notification channels must be unique"):
        DocumentTypeDefinition.model_validate(payload)


@pytest.mark.contract
def test_rejects_count_metric_with_value_field() -> None:
    payload = document_type_payload()
    metrics = payload["metrics"]
    assert isinstance(metrics, list)
    metrics[0]["field"] = "rating"

    with pytest.raises(ValidationError, match="count metrics cannot declare"):
        DocumentTypeDefinition.model_validate(payload)


@pytest.mark.contract
def test_rejects_multiple_default_views() -> None:
    payload = document_type_payload()
    views = payload["views"]
    assert isinstance(views, list)
    views[1]["default"] = True

    with pytest.raises(ValidationError, match="exactly one default view"):
        DocumentTypeDefinition.model_validate(payload)


@pytest.mark.contract
def test_rejects_unknown_sensitive_field() -> None:
    payload = document_type_payload()
    privacy = payload["privacy"]
    assert isinstance(privacy, dict)
    privacy["sensitiveFields"] = ["salary"]

    with pytest.raises(ValidationError, match="privacy policies must reference"):
        DocumentTypeDefinition.model_validate(payload)


@pytest.mark.contract
def test_exports_document_type_schema(tmp_path: Path) -> None:
    paths = export_contracts(tmp_path)
    schema_path = tmp_path / "document-type.schema.json"

    assert schema_path in paths
    assert '"$id": "https://schemas.kya.energy/platform/document-type/v1"' in (
        schema_path.read_text(encoding="utf-8")
    )
