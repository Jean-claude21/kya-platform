"""Operational examples remain valid and exercise governed business references."""

from pathlib import Path

import pytest

from kya_platform.contracts.document_type import DocumentTypeDefinition

ROOT = Path(__file__).parents[4]
EXAMPLES = ROOT / "specs" / "020-native-document-runtime" / "examples"


@pytest.mark.contract
@pytest.mark.parametrize(
    ("filename", "expected_resources"),
    [
        ("mission-request.document-type.json", {"person", "client", "project"}),
        (
            "equipment-movement.document-type.json",
            {"equipment", "person", "client", "site"},
        ),
    ],
)
def test_operational_document_examples_are_valid_and_reference_authorities(
    filename: str, expected_resources: set[str]
) -> None:
    definition = DocumentTypeDefinition.model_validate_json(
        (EXAMPLES / filename).read_text(encoding="utf-8")
    )

    assert {reference.resource_type for reference in definition.references} == expected_resources
    assert all(reference.required_permission for reference in definition.references)
    assert all(reference.snapshot_fields for reference in definition.references)
    assert definition.workflow.transitions
