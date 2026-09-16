"""The Skill Factory creates portable packages without executing their content."""

import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from kya_platform.application.artifact_registry.archive import ArchiveValidationError
from kya_platform.application.skill_factory import SkillBlueprint, SkillFactory
from kya_platform.contracts.artifact_package import PackageFileKind


def blueprint() -> SkillBlueprint:
    return SkillBlueprint(
        slug="kya-design-system",
        display_name="KYA Design System",
        description="Concevoir les interfaces KYA avec les règles visuelles validées.",
        business_owner="communication",
        technical_owner="cvsi-platform",
        workspace="group",
        repository="https://github.com/Jean-claude21/kya-platform",
        commit="a" * 40,
    )


def test_initializes_and_packages_a_discoverable_skill(tmp_path: Path) -> None:
    factory = SkillFactory()
    root = factory.initialize(tmp_path, blueprint())

    first, validated = factory.package(root)
    second, replay = factory.package(root)

    assert first == second
    assert validated.archive_digest == replay.archive_digest
    assert validated.package.artifact.artifact_id == "kya:skill:kya-design-system"
    assert {item.path: item.kind for item in validated.package.files}["agents/openai.yaml"] is (
        PackageFileKind.METADATA
    )
    with zipfile.ZipFile(BytesIO(first)) as archive:
        manifest = json.loads(archive.read("artifact.manifest.json"))
        assert manifest["integrity"]["digest"] != "0" * 64


def test_package_normalizes_text_files_for_cross_platform_archives(tmp_path: Path) -> None:
    factory = SkillFactory()
    root = factory.initialize(tmp_path, blueprint())
    skill = root / "SKILL.md"
    skill.write_bytes(skill.read_bytes().replace(b"\n", b"\r\n"))

    archive, _ = factory.package(root)

    with zipfile.ZipFile(BytesIO(archive)) as packaged:
        assert b"\r\n" not in packaged.read("SKILL.md")


def test_refuses_overwrite_and_unsupported_paths(tmp_path: Path) -> None:
    factory = SkillFactory()
    root = factory.initialize(tmp_path, blueprint())
    with pytest.raises(FileExistsError):
        factory.initialize(tmp_path, blueprint())
    (root / "README.md").write_text("not part of a Skill package", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported skill path"):
        factory.package(root)


def test_executable_skill_requires_capability_tests_and_sbom(tmp_path: Path) -> None:
    factory = SkillFactory()
    root = factory.initialize(tmp_path, blueprint())
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "render.py").write_text("print('render')\n", encoding="utf-8")

    with pytest.raises(ArchiveValidationError, match="capability manifest"):
        factory.package(root)


@pytest.mark.parametrize("slug", ["KYA-Design", "ab", "-invalid"])
def test_rejects_non_portable_skill_names(slug: str) -> None:
    values = blueprint()
    with pytest.raises(ValueError, match="skill slug"):
        SkillBlueprint(
            slug=slug,
            display_name=values.display_name,
            description=values.description,
            business_owner=values.business_owner,
            technical_owner=values.technical_owner,
            workspace=values.workspace,
            repository=values.repository,
            commit=values.commit,
        )
