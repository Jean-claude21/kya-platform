"""Non-Git-backed proposal package: content lives inline until a pull request merges.

Unlike `ArtifactPackage` (which references content already committed to Git via a commit SHA and
digest), a `ProposalPackage` carries the actual file bytes, because a proposal exists precisely to
let a non-developer contribute before any Git commit is required. Once a reviewer approves a
proposal, its files are written into a real pull request; only then does the content re-enter the
Git-backed `ArtifactPackage` contract used by the rest of the publication cycle.
"""

import base64
import re
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kya_platform.contracts.artifact_package import (
    MAX_PACKAGE_BYTES,
    MAX_PACKAGE_FILES,
    PackageFileKind,
)

_BASE64_PATTERN = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")


class StrictProposalContract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProposalFile(StrictProposalContract):
    path: str = Field(min_length=1, max_length=512)
    kind: PackageFileKind
    content_base64: str = Field(alias="contentBase64", min_length=0)

    @field_validator("content_base64")
    @classmethod
    def validate_base64(cls, value: str) -> str:
        if _BASE64_PATTERN.fullmatch(value) is None:
            raise ValueError("proposal file content must be base64-encoded")
        return value

    def decoded(self) -> bytes:
        return base64.b64decode(self.content_base64)


class ProposalPackage(StrictProposalContract):
    """A self-contained, non-executing bundle submitted before any Git commit exists."""

    schema_version: Annotated[str, Field(alias="schemaVersion")] = "1"
    files: Annotated[list[ProposalFile], Field(min_length=1, max_length=MAX_PACKAGE_FILES)]

    @model_validator(mode="after")
    def validate_package(self) -> Self:
        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("proposal file paths must be unique")
        total_size = sum(len(item.decoded()) for item in self.files)
        if total_size > MAX_PACKAGE_BYTES:
            raise ValueError("proposal package exceeds maximum uncompressed size")
        if not any(item.path == "SKILL.md" for item in self.files):
            raise ValueError("a proposal requires SKILL.md")
        return self


__all__ = ["ProposalFile", "ProposalPackage"]
