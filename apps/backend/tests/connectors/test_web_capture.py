"""Contract and security tests for the first real source connector."""

import json
from collections.abc import Mapping
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft202012Validator

from kya_platform.connectors.web_capture import (
    FetchedResource,
    WebCaptureConfig,
    WebCaptureConnector,
)
from kya_platform.connectors.web_capture.client import (
    HttpResourceFetcher,
    ResourceTooLargeError,
    UnsafeRemoteResponseError,
)
from kya_platform.connectors.web_capture.html import project_html

CONFIG = WebCaptureConfig(
    "https://kya-energy.com/fr",
    ("kya-energy.com",),
    max_pages=2,
    max_body_bytes=4096,
)


class FakeFetcher:
    def __init__(self, responses: Mapping[str, FetchedResource]) -> None:
        self.responses = responses

    async def fetch(self, url: str, config: WebCaptureConfig) -> FetchedResource:
        config.validate_url(url)
        try:
            return self.responses[url]
        except KeyError as error:
            raise UnsafeRemoteResponseError("fixture resource unavailable") from error


def resource(url: str, body: str, media_type: str = "text/html") -> FetchedResource:
    return FetchedResource(url, 200, media_type, body.encode(), '"v1"', "today")


@pytest.mark.unit
def test_configuration_rejects_external_insecure_and_ip_urls() -> None:
    with pytest.raises(ValueError, match="credential-free HTTPS"):
        CONFIG.validate_url("http://kya-energy.com/fr")
    with pytest.raises(ValueError, match="allowlist"):
        CONFIG.validate_url("https://example.com/")
    with pytest.raises(ValueError, match="IP literals"):
        WebCaptureConfig("https://127.0.0.1/", ("127.0.0.1",))


@pytest.mark.unit
def test_html_projection_keeps_raw_evidence_and_extracts_useful_fields() -> None:
    page = project_html(
        resource(
            CONFIG.seed_url,
            '<html lang="fr"><head><title>KYA Énergie</title>'
            '<link rel="canonical" href="/fr"></head><body><h1>Notre impact</h1>'
            '<script>secret noise</script><p>5 MWc installés</p><a href="/fr/produits">Voir</a>'
            '<a href="https://example.com">Externe</a></body></html>',
        )
    )
    assert page.title == "KYA Énergie"
    assert page.language == "fr"
    assert page.headings == ("Notre impact",)
    assert "5 MWc installés" in page.text
    assert "secret noise" not in page.text
    assert page.internal_links == ("https://kya-energy.com/fr/produits",)
    assert page.html.startswith("<html")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_capture_uses_robots_sitemap_bounds_and_is_canonical() -> None:
    robots = resource(
        "https://kya-energy.com/robots.txt",
        "User-agent: *\nAllow: /\nSitemap: https://kya-energy.com/sitemap.xml",
        "text/plain",
    )
    sitemap = resource(
        "https://kya-energy.com/sitemap.xml",
        "<urlset><url><loc>https://kya-energy.com/fr</loc></url>"
        "<url><loc>https://kya-energy.com/document.pdf</loc></url>"
        "<url><loc>https://kya-energy.com/fr/produits</loc></url>"
        "<url><loc>https://outside.test/ignored</loc></url></urlset>",
        "application/xml",
    )
    home = resource(CONFIG.seed_url, "<html><title>Accueil</title><h1>KYA</h1></html>")
    products = resource(
        "https://kya-energy.com/fr/produits", "<html><title>Produits</title></html>"
    )
    connector = WebCaptureConnector(
        FakeFetcher(
            {robots.url: robots, sitemap.url: sitemap, home.url: home, products.url: products}
        )
    )

    bundle = await connector.capture(CONFIG)

    assert [page.title for page in bundle.pages] == ["Accueil", "Produits"]
    assert [issue.code for issue in bundle.issues] == ["UnsafeRemoteResponseError"]
    assert bundle.to_bytes() == bundle.to_bytes()
    assert len(bundle.digest) == 64
    schema_path = (
        Path(__file__).parents[4]
        / "specs"
        / "006-kya-owned-web-connector"
        / "contracts"
        / "web-capture.schema.json"
    )
    Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8"))).validate(
        json.loads(bundle.to_bytes())
    )


@pytest.mark.asyncio
@pytest.mark.security
async def test_capture_fails_closed_when_robots_is_unavailable() -> None:
    connector = WebCaptureConnector(FakeFetcher({}))
    with pytest.raises(PermissionError, match="robots"):
        await connector.capture(CONFIG)


@pytest.mark.asyncio
@pytest.mark.security
async def test_http_fetcher_revalidates_redirects_and_bounds_body() -> None:
    def redirect(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://outside.test/private"})

    with pytest.raises(ValueError, match="allowlist"):
        await HttpResourceFetcher(httpx.MockTransport(redirect)).fetch(CONFIG.seed_url, CONFIG)

    def oversized(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "content-length": "5000"},
            content=b"x",
        )

    with pytest.raises(ResourceTooLargeError, match="declared"):
        await HttpResourceFetcher(httpx.MockTransport(oversized)).fetch(CONFIG.seed_url, CONFIG)
