"""Public KYA event and webhook integrity contracts."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from kya_platform.application.webhooks import sign_webhook, verify_webhook
from kya_platform.contracts.events import KyaEventEnvelope

EVENT_ID = UUID("01991c00-0000-7000-8000-000000000001")
CORRELATION_ID = UUID("01991c00-0000-7000-8000-000000000002")


def event_payload() -> dict[str, object]:
    return {
        "specversion": "1.0",
        "id": str(EVENT_ID),
        "type": "form.submitted",
        "source": "https://forms.kya.example",
        "subject": "form-submission/01991c00",
        "time": datetime(2026, 9, 18, 12, tzinfo=UTC).isoformat(),
        "datacontenttype": "application/json",
        "schemaVersion": "1",
        "context": {"unitId": "group", "workspaceId": "kya-platform"},
        "correlationId": str(CORRELATION_ID),
        "actorId": "01991c00-0000-7000-8000-000000000003",
        "data": {"submissionId": "01991c00"},
    }


@pytest.mark.contract
def test_event_envelope_preserves_context_and_traceability() -> None:
    event = KyaEventEnvelope.model_validate(event_payload())

    assert event.event_type == "form.submitted"
    assert event.context.unit_id == "group"
    assert event.correlation_id == CORRELATION_ID


@pytest.mark.contract
def test_event_envelope_rejects_unversioned_or_naive_events() -> None:
    payload = event_payload()
    payload["type"] = "submitted"
    payload["time"] = "2026-09-18T12:00:00"

    with pytest.raises(ValidationError):
        KyaEventEnvelope.model_validate(payload)


@pytest.mark.contract
def test_webhook_signature_is_deterministic_and_time_bounded() -> None:
    payload = b'{"type":"form.submitted"}'
    signature = sign_webhook(payload, b"reference-only-secret", timestamp=1_800_000_000)

    assert verify_webhook(
        payload,
        b"reference-only-secret",
        signature.header_value,
        now=1_800_000_120,
    )
    assert not verify_webhook(
        payload,
        b"reference-only-secret",
        signature.header_value,
        now=1_800_000_301,
    )
    assert not verify_webhook(
        payload + b"tampered",
        b"reference-only-secret",
        signature.header_value,
        now=1_800_000_120,
    )
