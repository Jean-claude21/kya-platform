"""Proof that catalog types cannot transport secret values."""

from datetime import UTC, datetime
from uuid import uuid7

import pytest
from pydantic import ValidationError

from kya_platform.secrets import SecretReference, SecretStatus


def valid_reference() -> dict[str, object]:
    return {
        "id": uuid7(),
        "provider": "infisical",
        "locator": "project/env/path",
        "key_name": "provider_api_key",
        "owner_scope": "workspace:platform",
        "purpose": "Publier une preview",
        "environment": "preview",
        "status": SecretStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }


@pytest.mark.security
def test_reference_contract_has_no_secret_value_field() -> None:
    reference = SecretReference.model_validate(valid_reference())

    assert "value" not in reference.model_dump()
    assert "secret" not in reference.model_dump()
    assert "value" not in SecretReference.model_json_schema()["properties"]


@pytest.mark.security
@pytest.mark.parametrize("field", ["value", "secret", "plaintext", "credential"])
def test_rejects_any_extra_secret_material(field: str) -> None:
    candidate = {**valid_reference(), field: "must-never-enter-the-catalog"}

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SecretReference.model_validate(candidate)


@pytest.mark.unit
def test_reference_is_immutable() -> None:
    reference = SecretReference.model_validate(valid_reference())

    with pytest.raises(ValidationError):
        reference.status = SecretStatus.REVOKED
