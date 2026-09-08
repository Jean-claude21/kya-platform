"""S3-compatible storage adapter tests, including immutable replay."""

from typing import Any

import pytest
from botocore.exceptions import ClientError
from pydantic import SecretStr

from kya_platform.connectors.web_capture import storage
from kya_platform.connectors.web_capture.storage import S3ImmutableObjectStore, S3StorageConfig


class Client:
    def __init__(self, *, precondition: bool = False, stored_digest: str = "a" * 64) -> None:
        self.precondition = precondition
        self.stored_digest = stored_digest

    async def put_object(self, **kwargs: object) -> dict[str, Any]:
        if self.precondition:
            raise ClientError(
                {"Error": {"Code": "PreconditionFailed", "Message": "exists"}}, "PutObject"
            )
        assert kwargs["IfNoneMatch"] == "*"
        return {"VersionId": "version-1"}

    async def head_object(self, **kwargs: object) -> dict[str, Any]:
        del kwargs
        return {"Metadata": {"sha256": self.stored_digest}, "ETag": '"existing"'}


class Context:
    def __init__(self, client: Client) -> None:
        self.client = client

    async def __aenter__(self) -> Client:
        return self.client

    async def __aexit__(self, *args: object) -> None:
        del args


class Session:
    client_instance: Client

    def __init__(self, **kwargs: object) -> None:
        assert kwargs["region_name"] == "us-east-2"

    def client(self, *args: object, **kwargs: object) -> Context:
        del args, kwargs
        return Context(self.client_instance)


def config() -> S3StorageConfig:
    return S3StorageConfig(
        "https://storage.example.test",
        "us-east-2",
        "kya-data",
        SecretStr("access"),
        SecretStr("secret"),
    )


@pytest.mark.unit
def test_storage_configuration_rejects_unsafe_values() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        S3StorageConfig("http://storage", "region", "bucket", SecretStr("a"), SecretStr("b"))
    with pytest.raises(ValueError, match="required"):
        S3StorageConfig("https://storage", "", "bucket", SecretStr("a"), SecretStr("b"))


@pytest.mark.asyncio
@pytest.mark.unit
async def test_storage_put_and_safe_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    digest = "a" * 64
    Session.client_instance = Client()
    monkeypatch.setattr(storage.aioboto3, "Session", Session)
    adapter = S3ImmutableObjectStore(config())
    stored = await adapter.put(
        object_key=f"raw/web/{digest}.json",
        content=b"evidence",
        media_type="application/json",
        digest=digest,
    )
    assert stored.version_id == "version-1"

    Session.client_instance = Client(precondition=True, stored_digest=digest)
    replay = await adapter.put(
        object_key=f"raw/web/{digest}.json",
        content=b"evidence",
        media_type="application/json",
        digest=digest,
    )
    assert replay.version_id == "existing"


@pytest.mark.asyncio
@pytest.mark.security
async def test_storage_rejects_unsafe_key_and_digest_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = S3ImmutableObjectStore(config())
    with pytest.raises(ValueError, match="content-addressed"):
        await adapter.put(
            object_key="raw/web/item.json", content=b"x", media_type="text/plain", digest="a" * 64
        )
    Session.client_instance = Client(precondition=True, stored_digest="b" * 64)
    monkeypatch.setattr(storage.aioboto3, "Session", Session)
    with pytest.raises(RuntimeError, match="collision"):
        await adapter.put(
            object_key=f"raw/web/{'a' * 64}.json",
            content=b"x",
            media_type="text/plain",
            digest="a" * 64,
        )
