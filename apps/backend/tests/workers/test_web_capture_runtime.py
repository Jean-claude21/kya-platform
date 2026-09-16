"""Runtime wiring remains fail-closed and disposable."""

from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from kya_platform.config import Settings
from kya_platform.infrastructure.infisical import ResolvedSecret
from kya_platform.workers import web_capture_runtime


@pytest.mark.asyncio
@pytest.mark.unit
async def test_runtime_refuses_incomplete_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        web_capture_runtime,
        "get_settings",
        lambda: SimpleNamespace(has_web_capture_configuration=False),
    )
    with pytest.raises(RuntimeError, match="incomplete"):
        await web_capture_runtime.serve()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_storage_configuration_is_resolved_from_infisical() -> None:
    values = {
        "KYA_OBJECT_STORAGE_ENDPOINT_URL": "https://storage.example.test",
        "KYA_OBJECT_STORAGE_REGION": "us-east-2",
        "KYA_OBJECT_STORAGE_BUCKET": "kya-data",
        "KYA_OBJECT_STORAGE_ACCESS_KEY_ID": "access",
        "KYA_OBJECT_STORAGE_SECRET_ACCESS_KEY": "secret",
    }

    class Resolver:
        async def resolve(self, key_name: str, *, at: object) -> ResolvedSecret:
            del at
            return ResolvedSecret(key_name, SecretStr(values[key_name]))

    settings = Settings(
        _env_file=None,
        database_url=SecretStr("postgresql://db"),
        web_capture_enabled=True,
        infisical_api_url="https://app.infisical.com",
        infisical_client_id="client",
        infisical_client_secret=SecretStr("identity-secret"),
        infisical_project_id="project",
    )

    config = await web_capture_runtime._resolve_storage_config(
        settings,
        Resolver(),  # type: ignore[arg-type]
    )

    assert config.endpoint_url == "https://storage.example.test"
    assert config.region == "us-east-2"
    assert config.bucket == "kya-data"
    assert config.provider == "neon"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_runtime_wires_dedicated_topic_and_disposes_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        has_web_capture_configuration=True,
        database_url=SecretStr("postgresql://db"),
        object_storage_endpoint_url="https://storage.example.test",
        object_storage_region="us-east-2",
        object_storage_bucket="kya-data",
        object_storage_access_key_id=SecretStr("access"),
        object_storage_secret_access_key=SecretStr("secret"),
    )

    class Engine:
        disposed = False

        async def dispose(self) -> None:
            self.disposed = True

    engine = Engine()
    captured: dict[str, object] = {}

    class Runner:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        async def run_forever(self, stop: object) -> None:
            del stop

    monkeypatch.setattr(web_capture_runtime, "get_settings", lambda: settings)
    monkeypatch.setattr(web_capture_runtime, "create_engine", lambda value: engine)
    monkeypatch.setattr(web_capture_runtime, "create_session_factory", lambda value: object())
    monkeypatch.setattr(web_capture_runtime, "SqlAlchemyDataRepository", lambda value: object())
    monkeypatch.setattr(web_capture_runtime, "SqlAlchemyContentRepository", lambda value: object())
    monkeypatch.setattr(
        web_capture_runtime, "SqlAlchemyIntelligenceRepository", lambda value: object()
    )
    monkeypatch.setattr(web_capture_runtime, "DataService", lambda value: object())
    monkeypatch.setattr(web_capture_runtime, "ContentService", lambda value: object())
    monkeypatch.setattr(
        web_capture_runtime, "IntelligenceService", lambda *args, **kwargs: object()
    )
    monkeypatch.setattr(
        web_capture_runtime, "DatabaseOutboxQueue", lambda *args, **kwargs: object()
    )
    monkeypatch.setattr(web_capture_runtime, "WorkerRunner", Runner)
    monkeypatch.setattr(
        web_capture_runtime, "WebCaptureWorker", lambda **kwargs: SimpleNamespace(handle=None)
    )
    monkeypatch.setattr(
        web_capture_runtime,
        "IntelligenceEvaluationWorker",
        lambda *args, **kwargs: SimpleNamespace(handle=None),
    )
    monkeypatch.setattr(web_capture_runtime, "WebCaptureConnector", lambda value: object())
    monkeypatch.setattr(web_capture_runtime, "HttpResourceFetcher", lambda: object())
    monkeypatch.setattr(web_capture_runtime, "S3ImmutableObjectStore", lambda value: object())

    await web_capture_runtime.serve()

    assert engine.disposed is True
    assert set(captured["handlers"]) == {  # type: ignore[arg-type]
        "kya.data.run.started.v1",
        "kya.data.run.completed.v1",
    }
