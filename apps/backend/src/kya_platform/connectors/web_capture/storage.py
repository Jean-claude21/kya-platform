"""Immutable object-store boundary and S3-compatible Neon adapter."""

from dataclasses import dataclass
from typing import Any, Protocol

import aioboto3
from botocore.exceptions import ClientError
from pydantic import SecretStr

from kya_platform.domain.data import StorageObject


class ImmutableObjectStore(Protocol):
    async def put(
        self, *, object_key: str, content: bytes, media_type: str, digest: str
    ) -> StorageObject: ...


@dataclass(frozen=True, slots=True)
class S3StorageConfig:
    endpoint_url: str
    region: str
    bucket: str
    access_key_id: SecretStr
    secret_access_key: SecretStr
    provider: str = "neon"

    def __post_init__(self) -> None:
        if not self.endpoint_url.startswith("https://"):
            raise ValueError("object storage endpoint must use HTTPS")
        if not self.region.strip() or not self.bucket.strip() or "/" in self.bucket:
            raise ValueError("object storage region and bucket are required")


class S3ImmutableObjectStore:
    """Put content-addressed objects; credentials are never returned or persisted in Data."""

    def __init__(self, config: S3StorageConfig) -> None:
        self._config = config

    async def put(
        self, *, object_key: str, content: bytes, media_type: str, digest: str
    ) -> StorageObject:
        if digest not in object_key or "?" in object_key or "://" in object_key:
            raise ValueError("immutable object keys must be safe and content-addressed")
        session = aioboto3.Session(
            aws_access_key_id=self._config.access_key_id.get_secret_value(),
            aws_secret_access_key=self._config.secret_access_key.get_secret_value(),
            region_name=self._config.region,
        )
        async with session.client("s3", endpoint_url=self._config.endpoint_url) as client:
            try:
                response: dict[str, Any] = await client.put_object(
                    Bucket=self._config.bucket,
                    Key=object_key,
                    Body=content,
                    ContentType=media_type,
                    Metadata={"sha256": digest},
                    IfNoneMatch="*",
                )
            except ClientError as error:
                code = str(error.response.get("Error", {}).get("Code", ""))
                if code not in {"PreconditionFailed", "412"}:
                    raise
                response = await client.head_object(Bucket=self._config.bucket, Key=object_key)
                metadata = response.get("Metadata", {})
                if metadata.get("sha256") != digest:
                    raise RuntimeError("immutable storage collision detected") from error
        version = response.get("VersionId") or response.get("ETag")
        return StorageObject(
            self._config.provider,
            self._config.bucket,
            object_key,
            str(version).strip('"') if version else None,
        )


__all__ = ["ImmutableObjectStore", "S3ImmutableObjectStore", "S3StorageConfig"]
