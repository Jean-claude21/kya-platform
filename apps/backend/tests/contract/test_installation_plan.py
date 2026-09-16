"""Installation plans remain deterministic, portable and client-consented."""

from uuid import UUID

import pytest

from kya_platform.contracts.artifact_manifest import ArtifactType
from kya_platform.contracts.installation_plan import (
    InstallationAction,
    InstallationProfile,
    InstallationScope,
    build_installation_plan,
    destination_for,
)

RELEASE_ID = UUID("01991b00-0000-7000-8000-000000000301")
ARTIFACT_ID = UUID("01991b00-0000-7000-8000-000000000302")


def build(*, profile: InstallationProfile, scope: InstallationScope):
    return build_installation_plan(
        release_id=RELEASE_ID,
        artifact_id=ARTIFACT_ID,
        artifact_type=ArtifactType.SKILL,
        artifact_slug="document-standard",
        version="1.0.0",
        profile=profile,
        scope=scope,
        target="workspace:dss",
        package_locator="git+https://github.com/kya-energy/skills@" + "a" * 40 + "#one",
        content_digest="b" * 64,
        compatibility_requirement=">=2026-09",
        client_version="2026-09",
        file_count=4,
        package_size=2048,
    )


@pytest.mark.parametrize(
    ("profile", "scope", "expected"),
    [
        (InstallationProfile.CODEX, InstallationScope.PERSONAL, "${CODEX_PERSONAL_SKILLS_DIR}"),
        (InstallationProfile.CODEX, InstallationScope.PROJECT, ".agents/skills"),
        (InstallationProfile.CLAUDE_CODE, InstallationScope.PERSONAL, "~/.claude/skills"),
        (InstallationProfile.CLAUDE_CODE, InstallationScope.PROJECT, ".claude/skills"),
        (
            InstallationProfile.PORTABLE_ZIP,
            InstallationScope.PERSONAL,
            "${USER_SELECTED_DIRECTORY}",
        ),
    ],
)
def test_destinations_are_symbolic_and_profile_specific(
    profile: InstallationProfile,
    scope: InstallationScope,
    expected: str,
) -> None:
    destination = destination_for(profile, scope, "document-standard", "1.0.0")

    assert destination.startswith(expected)
    assert "C:\\" not in destination


def test_same_immutable_release_and_target_produce_the_same_plan() -> None:
    first = build(profile=InstallationProfile.CODEX, scope=InstallationScope.PERSONAL)
    second = build(profile=InstallationProfile.CODEX, scope=InstallationScope.PERSONAL)

    assert first == second
    assert [step.action for step in first.steps] == list(InstallationAction)
    assert first.requires_client_confirmation is True
    assert first.server_writes_local_files is False
    assert first.integrity_locator.endswith(".integrity.json")
    assert first.steps[1].source == first.integrity_locator
    assert first.steps[2].source == first.integrity_locator
    assert all("secret" not in step.model_dump_json().lower() for step in first.steps)


def test_filesystem_agent_profiles_reject_non_skill_artifacts() -> None:
    with pytest.raises(ValueError, match="Skills only"):
        build_installation_plan(
            release_id=RELEASE_ID,
            artifact_id=ARTIFACT_ID,
            artifact_type=ArtifactType.MCP_SERVER,
            artifact_slug="scraper",
            version="1.0.0",
            profile=InstallationProfile.CODEX,
            scope=InstallationScope.PERSONAL,
            target="workspace:dss",
            package_locator="https://packages.kya.energy/scraper.zip",
            content_digest="b" * 64,
            compatibility_requirement=">=2026-09",
            client_version="2026-09",
            file_count=4,
            package_size=2048,
        )


def test_plan_rejects_mutable_or_unsupported_package_locations() -> None:
    with pytest.raises(ValueError, match="locator"):
        build_installation_plan(
            release_id=RELEASE_ID,
            artifact_id=ARTIFACT_ID,
            artifact_type=ArtifactType.SKILL,
            artifact_slug="document-standard",
            version="1.0.0",
            profile=InstallationProfile.PORTABLE_ZIP,
            scope=InstallationScope.PERSONAL,
            target="workspace:dss",
            package_locator="file:///unsafe/local.zip",
            content_digest="b" * 64,
            compatibility_requirement=">=1",
            client_version="2026-09",
            file_count=1,
            package_size=1,
        )


def test_plan_rejects_an_incompatible_client_version() -> None:
    with pytest.raises(ValueError, match="does not satisfy"):
        build_installation_plan(
            release_id=RELEASE_ID,
            artifact_id=ARTIFACT_ID,
            artifact_type=ArtifactType.SKILL,
            artifact_slug="document-standard",
            version="1.0.0",
            profile=InstallationProfile.CODEX,
            scope=InstallationScope.PERSONAL,
            target="workspace:dss",
            package_locator="https://packages.kya.energy/document-standard.zip",
            content_digest="b" * 64,
            compatibility_requirement=">=2027",
            client_version="2026-09",
            file_count=1,
            package_size=1,
        )
