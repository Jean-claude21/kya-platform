"""Command-line entry point for the KYA Skill Factory."""

import argparse
from pathlib import Path

from kya_platform.application.artifact_registry.archive import ArtifactArchiveValidator
from kya_platform.application.skill_factory import SkillBlueprint, SkillFactory


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kya-skill")
    commands = parser.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init", help="create a governed Skill source tree")
    initialize.add_argument("slug")
    initialize.add_argument("--destination", type=Path, required=True)
    initialize.add_argument("--name", required=True)
    initialize.add_argument("--description", required=True)
    initialize.add_argument("--business-owner", required=True)
    initialize.add_argument("--technical-owner", required=True)
    initialize.add_argument("--workspace", required=True)
    initialize.add_argument("--repository", required=True)
    initialize.add_argument("--commit", required=True)
    initialize.add_argument("--version", default="0.1.0")

    package = commands.add_parser("pack", help="build and validate a portable Skill ZIP")
    package.add_argument("source", type=Path)
    package.add_argument("--output", type=Path, required=True)

    validate = commands.add_parser("validate", help="validate a Skill ZIP without execution")
    validate.add_argument("archive", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    factory = SkillFactory()
    if arguments.command == "init":
        root = factory.initialize(
            arguments.destination,
            SkillBlueprint(
                slug=arguments.slug,
                display_name=arguments.name,
                description=arguments.description,
                business_owner=arguments.business_owner,
                technical_owner=arguments.technical_owner,
                workspace=arguments.workspace,
                repository=arguments.repository,
                commit=arguments.commit,
                version=arguments.version,
            ),
        )
        print(root)
        return 0
    if arguments.command == "pack":
        archive, validated = factory.package(arguments.source)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_bytes(archive)
        print(f"{validated.package.artifact.artifact_id}@{validated.package.artifact.version}")
        print(validated.archive_digest)
        return 0
    validated = ArtifactArchiveValidator().validate(arguments.archive.read_bytes())
    print(f"{validated.package.artifact.artifact_id}@{validated.package.artifact.version}")
    print(validated.archive_digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
