"""Provider-neutral contracts for one bounded web capture."""

import ipaddress
import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from urllib.parse import urlsplit


def _safe_https_url(value: str, allowed_hosts: tuple[str, ...]) -> str:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise ValueError("web capture URLs must be credential-free HTTPS URLs")
    if parsed.port not in (None, 443):
        raise ValueError("web capture URLs must use the standard HTTPS port")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("web capture URLs must not use IP literals")
    if host not in allowed_hosts:
        raise ValueError("web capture URL is outside the configured host allowlist")
    return value


@dataclass(frozen=True, slots=True)
class WebCaptureConfig:
    """Immutable policy for a single owned web property."""

    seed_url: str
    allowed_hosts: tuple[str, ...]
    user_agent: str = "KYA-Platform-WebCapture/0.1 (+https://kya-energy.com/fr)"
    max_pages: int = 25
    max_body_bytes: int = 2_000_000
    max_capture_bytes: int = 50_000_000
    max_redirects: int = 3
    request_timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        normalized = tuple(sorted({host.strip().casefold() for host in self.allowed_hosts}))
        if not normalized or any(not host or ":" in host or "/" in host for host in normalized):
            raise ValueError("allowed_hosts must contain DNS hostnames only")
        object.__setattr__(self, "allowed_hosts", normalized)
        _safe_https_url(self.seed_url, normalized)
        if not self.user_agent.strip() or len(self.user_agent) > 240:
            raise ValueError("a bounded explicit user agent is required")
        if not 1 <= self.max_pages <= 100:
            raise ValueError("max_pages must be between 1 and 100")
        if not 1_024 <= self.max_body_bytes <= 10_000_000:
            raise ValueError("max_body_bytes must be between 1024 and 10000000")
        if not self.max_body_bytes <= self.max_capture_bytes <= 100_000_000:
            raise ValueError("max_capture_bytes must be between one body and 100000000")
        if not 0 <= self.max_redirects <= 10:
            raise ValueError("max_redirects must be between 0 and 10")
        if not 1 <= self.request_timeout_seconds <= 60:
            raise ValueError("request timeout must be between 1 and 60 seconds")

    def validate_url(self, url: str) -> str:
        return _safe_https_url(url, self.allowed_hosts)


@dataclass(frozen=True, slots=True)
class FetchedResource:
    url: str
    status_code: int
    media_type: str
    body: bytes
    etag: str | None = None
    last_modified: str | None = None


@dataclass(frozen=True, slots=True)
class CapturedPage:
    url: str
    status_code: int
    media_type: str
    body_sha256: str
    content_trust: str
    html: str
    title: str | None
    language: str | None
    canonical_url: str | None
    headings: tuple[str, ...]
    text: str
    internal_links: tuple[str, ...]
    etag: str | None = None
    last_modified: str | None = None


@dataclass(frozen=True, slots=True)
class CaptureIssue:
    url: str
    code: str


@dataclass(frozen=True, slots=True)
class CaptureBundle:
    schema_version: str
    source_url: str
    pages: tuple[CapturedPage, ...]
    issues: tuple[CaptureIssue, ...] = ()

    def to_bytes(self) -> bytes:
        return json.dumps(
            asdict(self),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return sha256(self.to_bytes()).hexdigest()


__all__ = [
    "CaptureBundle",
    "CaptureIssue",
    "CapturedPage",
    "FetchedResource",
    "WebCaptureConfig",
]
