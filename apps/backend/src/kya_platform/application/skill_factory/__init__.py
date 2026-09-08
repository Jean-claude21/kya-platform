"""Deterministic authoring and packaging for governed KYA Skills."""

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from kya_platform.application.artifact_registry.archive import (
    ArtifactArchiveValidator,
    ValidatedArchive,
    calculate_payload_digest,
)
from kya_platform.contracts.artifact_package import PackageFile, PackageFileKind

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
_COMMIT = re.compile(r"^[a-fA-F0-9]{40}$")
_ALLOWED_ROOTS = frozenset(
    {"agents", "references", "assets", "templates", "scripts", "tests", "schemas", "examples"}
)


@dataclass(frozen=True, slots=True)
class SkillBlueprint:
    slug: str
    display_name: str
    description: str
    business_owner: str
    technical_owner: str
    workspace: str
    repository: str
    commit: str
    version: str = "0.1.0"

    def __post_init__(self) -> None:
        if _SLUG.fullmatch(self.slug) is None:
            raise ValueError("skill slug must contain 3 to 64 lowercase letters, digits or hyphens")
        if _COMMIT.fullmatch(self.commit) is None:
            raise ValueError("source commit must be a full 40-character Git SHA")
        required = (
            self.display_name,
            self.description,
            self.business_owner,
            self.technical_owner,
            self.workspace,
            self.repository,
        )
        if any(not value.strip() for value in required):
            raise ValueError("skill blueprint fields must be non-empty")


class SkillFactory:
    """Create source trees and portable archives without executing packaged content."""

    def initialize(self, destination: Path, blueprint: SkillBlueprint) -> Path:
        root = destination.resolve() / blueprint.slug
        if root.exists():
            raise FileExistsError(f"skill already exists: {root}")
        root.mkdir(parents=True)
        (root / "agents").mkdir()
        skill = (
            "---\n"
            f"name: {blueprint.slug}\n"
            f"description: {json.dumps(blueprint.description.strip(), ensure_ascii=False)}\n"
            "---\n\n"
            f"# {blueprint.display_name.strip()}\n\n"
            "Apply the validated KYA method and load only the references required "
            "for the request.\n"
        ).encode()
        agent = (
            "interface:\n"
            f"  display_name: {json.dumps(blueprint.display_name, ensure_ascii=False)}\n"
            f"  short_description: {json.dumps(blueprint.description, ensure_ascii=False)}\n"
            f"  default_prompt: {json.dumps(f'Use ${blueprint.slug} for this request.')}\n"
        ).encode()
        (root / "SKILL.md").write_bytes(skill)
        (root / "agents" / "openai.yaml").write_bytes(agent)
        manifest = self._manifest(blueprint, root)
        (root / "artifact.manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return root

    def package(self, source: Path) -> tuple[bytes, ValidatedArchive]:
        root = source.resolve()
        manifest_path = root / "artifact.manifest.json"
        if not manifest_path.is_file():
            raise ValueError("artifact.manifest.json is required")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        contents = self._read_contents(root)
        files = self._inventory(contents)
        manifest["integrity"]["digest"] = calculate_payload_digest(files)
        contents["artifact.manifest.json"] = (
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        ).encode()
        archive = self._zip(contents)
        return archive, ArtifactArchiveValidator().validate(archive)

    @staticmethod
    def _manifest(blueprint: SkillBlueprint, root: Path) -> dict[str, object]:
        digest = hashlib.sha256(
            json.dumps(
                [
                    {
                        "path": path,
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "size": len(content),
                    }
                    for path, content in sorted(SkillFactory._read_contents(root).items())
                    if path != "artifact.manifest.json"
                ],
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return {
            "schemaVersion": "1",
            "id": f"kya:skill:{blueprint.slug}",
            "type": "skill",
            "name": blueprint.display_name,
            "version": blueprint.version,
            "summary": blueprint.description,
            "owners": {
                "business": blueprint.business_owner,
                "technical": blueprint.technical_owner,
                "workspace": blueprint.workspace,
            },
            "source": {
                "repository": blueprint.repository,
                "commit": blueprint.commit,
                "path": f"skills/{blueprint.slug}",
            },
            "integrity": {"algorithm": "sha256", "digest": digest},
            "compatibility": {"codex": ">=2026-09", "claude-code": ">=1"},
            "dependencies": [],
            "scopes": ["skill.discover"],
            "risk": "read",
        }

    @staticmethod
    def _read_contents(root: Path) -> dict[str, bytes]:
        contents: dict[str, bytes] = {}
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"symbolic links are forbidden: {path}")
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            first = PurePosixPath(relative).parts[0]
            if (
                relative
                not in {
                    "SKILL.md",
                    "artifact.manifest.json",
                    "capability.manifest.json",
                    "sbom.cdx.json",
                }
                and first not in _ALLOWED_ROOTS
            ):
                raise ValueError(f"unsupported skill path: {relative}")
            contents[relative] = path.read_bytes()
        return contents

    @staticmethod
    def _inventory(contents: dict[str, bytes]) -> list[PackageFile]:
        def kind(path: str) -> PackageFileKind:
            if path == "SKILL.md":
                return PackageFileKind.INSTRUCTION
            if path.startswith("agents/"):
                return PackageFileKind.METADATA
            if path.startswith("scripts/"):
                return PackageFileKind.SCRIPT
            if path.startswith("tests/"):
                return PackageFileKind.TEST
            if path.startswith("assets/"):
                return PackageFileKind.ASSET
            if path.startswith("templates/"):
                return PackageFileKind.TEMPLATE
            if path.startswith("schemas/"):
                return PackageFileKind.SCHEMA
            if path.startswith(("references/", "examples/")):
                return PackageFileKind.REFERENCE
            return PackageFileKind.MANIFEST

        return [
            PackageFile(
                path=path,
                media_type="application/octet-stream",
                size=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                kind=kind(path),
                executable=kind(path) is PackageFileKind.SCRIPT,
            )
            for path, content in sorted(contents.items())
        ]

    @staticmethod
    def _zip(contents: dict[str, bytes]) -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path, content in sorted(contents.items()):
                info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o100644 & 0xFFFF) << 16
                info.create_system = 3
                archive.writestr(info, content)
        return stream.getvalue()


__all__ = ["SkillBlueprint", "SkillFactory"]
