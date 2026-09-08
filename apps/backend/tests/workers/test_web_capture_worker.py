"""End-to-end orchestration test from outbox payload to governed snapshot."""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest

from kya_platform.application.data import DataService, RunCompletion
from kya_platform.connectors.web_capture import (
    FetchedResource,
    WebCaptureConfig,
    WebCaptureConnector,
)
from kya_platform.connectors.web_capture.storage import ImmutableObjectStore
from kya_platform.domain.data import IngestionRun, RunStatus, StorageObject
from kya_platform.workers.web_capture import WebCaptureWorker

RUN = UUID("01993490-0000-7000-8000-000000000001")
PIPELINE = UUID("01993490-0000-7000-8000-000000000002")
ACTOR = UUID("01993490-0000-7000-8000-000000000003")
ASSET = UUID("01993490-0000-7000-8000-000000000004")
CONTRACT = UUID("01993490-0000-7000-8000-000000000005")
CORRELATION = UUID("01993490-0000-7000-8000-000000000006")
NOW = datetime(2026, 9, 8, tzinfo=UTC)


class Fetcher:
    async def fetch(self, url: str, config: WebCaptureConfig) -> FetchedResource:
        config.validate_url(url)
        if url.endswith("robots.txt"):
            return FetchedResource(url, 200, "text/plain", b"User-agent: *\nAllow: /")
        if url.endswith("sitemap.xml"):
            return FetchedResource(url, 200, "application/xml", b"<urlset></urlset>")
        return FetchedResource(url, 200, "text/html", b"<html><h1>KYA</h1></html>")


class Store:
    content: bytes | None = None
    key: str | None = None

    async def put(
        self, *, object_key: str, content: bytes, media_type: str, digest: str
    ) -> StorageObject:
        assert media_type == "application/vnd.kya.web-capture+json"
        assert digest in object_key
        self.content = content
        self.key = object_key
        return StorageObject("neon", "kya-data", object_key, "v1")


class Data:
    completion: RunCompletion | None = None

    async def get_run(self, unit_key: str, run_id: UUID) -> IngestionRun | None:
        assert unit_key == "direction-cvsi"
        assert run_id == RUN
        return IngestionRun(RUN, PIPELINE, ACTOR, RunStatus.STARTED, NOW)

    async def complete_run(
        self, unit_key: str, completion: RunCompletion, *, command: object
    ) -> RunCompletion:
        del command
        assert unit_key == "direction-cvsi"
        self.completion = completion
        return completion


@pytest.mark.asyncio
@pytest.mark.integration
async def test_worker_persists_before_completing_governed_run() -> None:
    data = Data()
    store = Store()
    worker = WebCaptureWorker(
        data=cast(DataService, data),
        connector=WebCaptureConnector(Fetcher()),
        storage=cast(ImmutableObjectStore, store),
    )
    await worker.handle(
        {
            "aggregate_id": str(RUN),
            "unit_key": "direction-cvsi",
            "asset_id": str(ASSET),
            "contract_id": str(CONTRACT),
            "correlation_id": str(CORRELATION),
            "source_configuration": {
                "seed_url": "https://kya-energy.com/fr",
                "allowed_hosts": ["kya-energy.com"],
                "max_pages": 5,
            },
        }
    )

    assert store.content is not None
    assert store.key is not None
    assert data.completion is not None
    assert data.completion.run.status is RunStatus.COMPLETED
    assert data.completion.snapshot.storage.object_key == store.key
    assert data.completion.snapshot.row_count == 1
    assert {result.rule_key for result in data.completion.quality_results} == {
        "pages-present",
        "http-success",
        "urls-unique",
        "fetch-complete",
    }
