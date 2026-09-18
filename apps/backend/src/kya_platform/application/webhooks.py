"""Deterministic HMAC signatures for outbound KYA webhook deliveries."""

import hashlib
import hmac
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WebhookSignature:
    timestamp: int
    digest: str

    @property
    def header_value(self) -> str:
        return f"t={self.timestamp},v1={self.digest}"


def sign_webhook(
    payload: bytes, secret: bytes, *, timestamp: int | None = None
) -> WebhookSignature:
    if not secret:
        raise ValueError("A webhook signing secret is required")
    signed_at = int(time.time()) if timestamp is None else timestamp
    message = str(signed_at).encode() + b"." + payload
    return WebhookSignature(
        timestamp=signed_at,
        digest=hmac.new(secret, message, hashlib.sha256).hexdigest(),
    )


def verify_webhook(
    payload: bytes,
    secret: bytes,
    signature_header: str,
    *,
    now: int | None = None,
    tolerance_seconds: int = 300,
) -> bool:
    try:
        parts = dict(part.split("=", 1) for part in signature_header.split(","))
        timestamp = int(parts["t"])
        supplied = parts["v1"]
    except KeyError, ValueError:
        return False
    current_time = int(time.time()) if now is None else now
    if tolerance_seconds < 0 or abs(current_time - timestamp) > tolerance_seconds:
        return False
    expected = sign_webhook(payload, secret, timestamp=timestamp)
    return hmac.compare_digest(expected.digest, supplied)


__all__ = ["WebhookSignature", "sign_webhook", "verify_webhook"]
