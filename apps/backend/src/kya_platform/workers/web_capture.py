"""Outbox handler that turns one governed run into an immutable web snapshot."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid7

from kya_platform.application.data import CommandMetadata, DataService, RunCompletion
from kya_platform.application.reliability import JsonValue, canonical_request_hash
from kya_platform.connectors.web_capture import WebCaptureConfig, WebCaptureConnector
from kya_platform.connectors.web_capture.content import project_capture_content
from kya_platform.connectors.web_capture.storage import ImmutableObjectStore
from kya_platform.domain.data import DataSnapshot, QualityResult, QualityStatus


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"web capture payload requires {key}")
    return value


class WebCaptureWorker:
    def __init__(
        self,
        *,
        data: DataService,
        connector: WebCaptureConnector,
        storage: ImmutableObjectStore,
    ) -> None:
        self._data = data
        self._connector = connector
        self._storage = storage

    async def handle(self, payload: Mapping[str, object]) -> None:
        unit_key = _required_text(payload, "unit_key")
        run_id = UUID(_required_text(payload, "aggregate_id"))
        asset_id = UUID(_required_text(payload, "asset_id"))
        contract_id = UUID(_required_text(payload, "contract_id"))
        correlation_id = UUID(_required_text(payload, "correlation_id"))
        raw_config = payload.get("source_configuration")
        if not isinstance(raw_config, Mapping):
            raise ValueError("web capture source configuration is missing")
        seed_url = raw_config.get("seed_url")
        allowed_hosts = raw_config.get("allowed_hosts")
        if (
            not isinstance(seed_url, str)
            or not isinstance(allowed_hosts, list)
            or not all(isinstance(item, str) for item in allowed_hosts)
        ):
            raise ValueError("web capture source configuration is invalid")
        config = WebCaptureConfig(
            seed_url=seed_url,
            allowed_hosts=tuple(cast(list[str], allowed_hosts)),
            max_pages=int(raw_config.get("max_pages", 25)),
            max_capture_bytes=int(raw_config.get("max_capture_bytes", 50_000_000)),
        )
        run = await self._data.get_run(unit_key, run_id)
        if run is None:
            raise ValueError("web capture run is outside the governed unit")

        bundle = await self._connector.capture(config)
        content = bundle.to_bytes()
        object_key = f"raw/web/{asset_id}/{bundle.digest}.json"
        stored = await self._storage.put(
            object_key=object_key,
            content=content,
            media_type="application/vnd.kya.web-capture+json",
            digest=bundle.digest,
        )
        completed_at = datetime.now(UTC)
        snapshot = DataSnapshot(
            uuid7(),
            asset_id,
            run.id,
            contract_id,
            stored,
            bundle.digest,
            "application/vnd.kya.web-capture+json",
            completed_at,
            len(bundle.pages),
            len(content),
        )
        completion = RunCompletion(
            run.complete(completed_at),
            snapshot,
            (
                QualityResult("pages-present", QualityStatus.PASSED, {"count": len(bundle.pages)}),
                QualityResult(
                    "http-success",
                    QualityStatus.PASSED,
                    {"statuses": sorted({page.status_code for page in bundle.pages})},
                ),
                QualityResult(
                    "urls-unique",
                    QualityStatus.PASSED,
                    {"count": len({page.url for page in bundle.pages})},
                ),
                QualityResult(
                    "fetch-complete",
                    QualityStatus.PASSED if not bundle.issues else QualityStatus.WARNING,
                    {
                        "issues": len(bundle.issues),
                        "codes": sorted({issue.code for issue in bundle.issues}),
                    },
                ),
            ),
            content_documents=project_capture_content(snapshot.id, bundle),
        )
        command_payload: dict[str, JsonValue] = {
            "run_id": str(run.id),
            "content_digest": bundle.digest,
        }
        await self._data.complete_run(
            unit_key,
            completion,
            command=CommandMetadata(
                actor_id=run.triggered_by,
                correlation_id=correlation_id,
                idempotency_key=f"web-capture-complete:{run.id}",
                request_hash=canonical_request_hash(command_payload),
                expires_at=completed_at + timedelta(days=7),
            ),
        )


__all__ = ["WebCaptureWorker"]
