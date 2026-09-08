"""Bounded connector for KYA-owned institutional websites."""

from kya_platform.connectors.web_capture.capture import WebCaptureConnector
from kya_platform.connectors.web_capture.contracts import (
    CaptureBundle,
    CapturedPage,
    CaptureIssue,
    FetchedResource,
    WebCaptureConfig,
)

__all__ = [
    "CaptureBundle",
    "CaptureIssue",
    "CapturedPage",
    "FetchedResource",
    "WebCaptureConfig",
    "WebCaptureConnector",
]
