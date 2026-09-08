"""HTTP adapter that validates every hop and bounds every response."""

from collections.abc import AsyncIterator
from typing import Protocol
from urllib.parse import urljoin

import httpx

from kya_platform.connectors.web_capture.contracts import FetchedResource, WebCaptureConfig

_REDIRECTS = {301, 302, 303, 307, 308}
_ALLOWED_MEDIA_TYPES = {
    "text/html",
    "text/plain",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
}


class ResourceFetcher(Protocol):
    async def fetch(self, url: str, config: WebCaptureConfig) -> FetchedResource: ...


class ResourceTooLargeError(RuntimeError):
    """The remote body exceeded the configured hard limit."""


class UnsafeRemoteResponseError(RuntimeError):
    """The remote endpoint returned an unsafe redirect or content type."""


async def _bounded_body(chunks: AsyncIterator[bytes], maximum: int) -> bytes:
    body = bytearray()
    async for chunk in chunks:
        body.extend(chunk)
        if len(body) > maximum:
            raise ResourceTooLargeError("remote body exceeds the configured limit")
    return bytes(body)


class HttpResourceFetcher:
    """Fetch public owned content without ambient proxy credentials or automatic redirects."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def fetch(self, url: str, config: WebCaptureConfig) -> FetchedResource:
        current = config.validate_url(url)
        headers = {"User-Agent": config.user_agent, "Accept": "text/html,application/xml;q=0.9"}
        timeout = httpx.Timeout(config.request_timeout_seconds)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            transport=self._transport,
        ) as client:
            for hop in range(config.max_redirects + 1):
                async with client.stream("GET", current, headers=headers) as response:
                    if response.status_code in _REDIRECTS:
                        location = response.headers.get("location")
                        if not location or hop == config.max_redirects:
                            raise UnsafeRemoteResponseError("redirect chain is invalid or too long")
                        current = config.validate_url(urljoin(current, location))
                        continue
                    response.raise_for_status()
                    media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                    if media_type not in _ALLOWED_MEDIA_TYPES:
                        raise UnsafeRemoteResponseError("remote content type is not allowed")
                    declared = response.headers.get("content-length")
                    if declared and int(declared) > config.max_body_bytes:
                        raise ResourceTooLargeError(
                            "declared remote body exceeds the configured limit"
                        )
                    body = await _bounded_body(response.aiter_bytes(), config.max_body_bytes)
                    return FetchedResource(
                        url=str(response.url),
                        status_code=response.status_code,
                        media_type=media_type,
                        body=body,
                        etag=response.headers.get("etag"),
                        last_modified=response.headers.get("last-modified"),
                    )
        raise UnsafeRemoteResponseError("redirect chain did not yield content")


__all__ = [
    "HttpResourceFetcher",
    "ResourceFetcher",
    "ResourceTooLargeError",
    "UnsafeRemoteResponseError",
]
