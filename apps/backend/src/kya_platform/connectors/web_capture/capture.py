"""Deterministic crawl policy for one KYA-owned web property."""

from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import httpx

from kya_platform.connectors.web_capture.client import (
    ResourceFetcher,
    ResourceTooLargeError,
    UnsafeRemoteResponseError,
)
from kya_platform.connectors.web_capture.contracts import (
    CaptureBundle,
    CaptureIssue,
    WebCaptureConfig,
)
from kya_platform.connectors.web_capture.html import project_html


def _sitemap_urls(body: bytes) -> tuple[str, ...]:
    root = ElementTree.fromstring(body)  # noqa: S314 -- input is size-bounded before parsing
    return tuple(
        node.text.strip()
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] == "loc" and node.text and node.text.strip()
    )


class WebCaptureConnector:
    def __init__(self, fetcher: ResourceFetcher) -> None:
        self._fetcher = fetcher

    async def capture(self, config: WebCaptureConfig) -> CaptureBundle:
        robots_url = urljoin(config.seed_url, "/robots.txt")
        robots = RobotFileParser()
        try:
            resource = await self._fetcher.fetch(robots_url, config)
        except httpx.HTTPStatusError as error:
            if 400 <= error.response.status_code < 500:
                robots.parse(["User-agent: *", "Allow: /"])
            else:
                robots.parse(["User-agent: *", "Disallow: /"])
        except httpx.HTTPError, RuntimeError, ValueError:
            robots.parse(["User-agent: *", "Disallow: /"])
        else:
            robots.parse(resource.body.decode("utf-8", errors="replace").splitlines())

        if not robots.can_fetch(config.user_agent, config.seed_url):
            raise PermissionError("robots policy forbids the configured seed URL")

        candidates: list[str] = []
        sitemap_url = urljoin(config.seed_url, "/sitemap.xml")
        if robots.can_fetch(config.user_agent, sitemap_url):
            try:
                sitemap = await self._fetcher.fetch(sitemap_url, config)
                candidates.extend(_sitemap_urls(sitemap.body))
            except ElementTree.ParseError, httpx.HTTPError, RuntimeError, ValueError:
                candidates = []
        candidates.append(config.seed_url)

        pages = []
        issues: list[CaptureIssue] = []
        captured_bytes = 0
        seen: set[str] = set()
        for candidate in candidates:
            try:
                safe_url = config.validate_url(candidate)
            except ValueError:
                continue
            normalized = safe_url.split("#", 1)[0]
            if normalized in seen or not robots.can_fetch(config.user_agent, normalized):
                continue
            seen.add(normalized)
            try:
                resource = await self._fetcher.fetch(normalized, config)
            except (httpx.HTTPError, ResourceTooLargeError, UnsafeRemoteResponseError) as error:
                if normalized == config.seed_url:
                    raise
                issues.append(CaptureIssue(normalized, type(error).__name__))
                continue
            if resource.media_type not in {"text/html", "application/xhtml+xml"}:
                continue
            if captured_bytes + len(resource.body) > config.max_capture_bytes:
                issues.append(CaptureIssue(normalized, "CaptureBudgetExceeded"))
                break
            page = project_html(resource)
            pages.append(page)
            captured_bytes += len(resource.body)
            candidates.extend(page.internal_links)
            if len(pages) >= config.max_pages:
                break

        if not pages:
            raise RuntimeError("web capture produced no HTML page")
        return CaptureBundle("1.0", config.seed_url, tuple(pages), tuple(issues))


__all__ = ["WebCaptureConnector"]
