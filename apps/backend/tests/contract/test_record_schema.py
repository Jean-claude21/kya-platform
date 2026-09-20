"""Stable generic schema contract for records owned by KYA applications."""

import pytest
from pydantic import ValidationError

from kya_platform.contracts.record_schema import RecordSchema


def schema_payload() -> dict[str, object]:
    return {
        "schemaVersion": "1",
        "id": "kya:data-schema:site-inspection",
        "version": "1.0.0",
        "name": "Inspection de site",
        "ownerScope": "workspace:operations",
        "fields": [
            {"key": "title", "label": "Titre", "type": "text", "required": True},
            {
                "key": "site",
                "label": "Site",
                "type": "relation",
                "relation": {
                    "targetSchemaId": "kya:data-schema:site",
                    "cardinality": "many-to-one",
                },
            },
            {
                "key": "evidence",
                "label": "Preuves",
                "type": "attachment",
                "multiple": True,
                "attachment": {
                    "maxFiles": 10,
                    "maxBytesPerFile": 10_000_000,
                    "allowedMediaTypes": ["image/jpeg", "application/pdf"],
                },
            },
        ],
        "access": {
            "enforcement": "record",
            "permissions": ["view", "create", "edit", "share"],
        },
        "retention": {
            "retainDays": 2555,
            "softDeleteDays": 30,
            "legalHoldSupported": True,
        },
    }


@pytest.mark.contract
def test_accepts_fields_relations_attachments_retention_and_record_permissions() -> None:
    schema = RecordSchema.model_validate(schema_payload())

    assert schema.schema_id == "kya:data-schema:site-inspection"
    assert schema.access.enforcement == "record"
    assert schema.fields[1].relation is not None
    assert schema.fields[2].attachment is not None


@pytest.mark.contract
def test_rejects_type_specific_configuration_on_wrong_field() -> None:
    payload = schema_payload()
    fields = payload["fields"]
    assert isinstance(fields, list)
    first = fields[0]
    assert isinstance(first, dict)
    first["choices"] = ["unexpected"]

    with pytest.raises(ValidationError, match="only choice fields"):
        RecordSchema.model_validate(payload)


@pytest.mark.contract
def test_rejects_duplicate_field_keys() -> None:
    payload = schema_payload()
    fields = payload["fields"]
    assert isinstance(fields, list)
    fields.append({"key": "title", "label": "Titre bis", "type": "text"})

    with pytest.raises(ValidationError, match="field keys"):
        RecordSchema.model_validate(payload)
