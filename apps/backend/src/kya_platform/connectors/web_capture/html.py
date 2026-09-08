"""Small deterministic HTML projection; raw HTML remains the evidence."""

from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from kya_platform.connectors.web_capture.contracts import CapturedPage, FetchedResource


class _ProjectionParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.headings: list[str] = []
        self.links: set[str] = set()
        self.language: str | None = None
        self.canonical_url: str | None = None
        self._ignored_depth = 0
        self._title_depth = 0
        self._heading_depth = 0
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "html":
            self.language = attributes.get("lang") or self.language
        if tag in {"script", "style", "template", "noscript"}:
            self._ignored_depth += 1
        if tag == "title":
            self._title_depth += 1
        if tag in {"h1", "h2", "h3"}:
            self._heading_depth += 1
            self._heading_parts = []
        if tag == "link" and (attributes.get("rel") or "").casefold() == "canonical":
            href = attributes.get("href")
            if href:
                self.canonical_url = urljoin(self.base_url, href)
        if tag == "a":
            href = attributes.get("href")
            if href:
                absolute = urljoin(self.base_url, href).split("#", 1)[0]
                if urlsplit(absolute).hostname == urlsplit(self.base_url).hostname:
                    self.links.add(absolute)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "template", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
        if tag in {"h1", "h2", "h3"} and self._heading_depth:
            heading = " ".join(self._heading_parts).strip()
            if heading:
                self.headings.append(heading)
            self._heading_depth -= 1
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        normalized = " ".join(data.split())
        if not normalized:
            return
        self.text_parts.append(normalized)
        if self._title_depth:
            self.title_parts.append(normalized)
        if self._heading_depth:
            self._heading_parts.append(normalized)


def project_html(resource: FetchedResource) -> CapturedPage:
    html = resource.body.decode("utf-8", errors="replace")
    parser = _ProjectionParser(resource.url)
    parser.feed(html)
    from hashlib import sha256

    return CapturedPage(
        url=resource.url,
        status_code=resource.status_code,
        media_type=resource.media_type,
        body_sha256=sha256(resource.body).hexdigest(),
        content_trust="untrusted_external_content",
        html=html,
        title=" ".join(parser.title_parts) or None,
        language=parser.language,
        canonical_url=parser.canonical_url,
        headings=tuple(parser.headings),
        text="\n".join(parser.text_parts),
        internal_links=tuple(sorted(parser.links)),
        etag=resource.etag,
        last_modified=resource.last_modified,
    )


__all__ = ["project_html"]
