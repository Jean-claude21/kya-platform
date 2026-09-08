"""The Skill Factory CLI exposes the same deterministic application service."""

from pathlib import Path

import pytest

from kya_platform.skill_factory_cli import main


def test_cli_initializes_packages_and_validates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "sources"
    archive = tmp_path / "dist" / "skill.zip"
    common = [
        "kya-design-system",
        "--destination",
        str(source),
        "--name",
        "KYA Design System",
        "--description",
        "Concevoir les interfaces KYA.",
        "--business-owner",
        "communication",
        "--technical-owner",
        "cvsi-platform",
        "--workspace",
        "group",
        "--repository",
        "https://github.com/Jean-claude21/kya-platform",
        "--commit",
        "a" * 40,
    ]

    assert main(["init", *common]) == 0
    assert main(["pack", str(source / "kya-design-system"), "--output", str(archive)]) == 0
    assert main(["validate", str(archive)]) == 0
    assert archive.is_file()
    assert "kya:skill:kya-design-system@0.1.0" in capsys.readouterr().out
