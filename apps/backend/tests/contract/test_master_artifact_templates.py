"""Keep governed artifact templates visible, complete and structurally stable."""

import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[4]


def test_master_skill_template_has_required_discovery_and_method_files() -> None:
    root = REPOSITORY_ROOT / "catalog" / "templates" / "skill" / "kya-business-method"
    expected = {
        "SKILL.md",
        "agents/openai.yaml",
        "artifact.manifest.json",
        "references/method.md",
    }

    assert {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    } == expected
    manifest = json.loads((root / "artifact.manifest.json").read_text(encoding="utf-8"))
    assert manifest["type"] == "skill"
    assert manifest["source"]["path"].startswith("catalog/sources/skills/")


def test_master_mcp_template_separates_contract_service_delivery_and_evidence() -> None:
    root = REPOSITORY_ROOT / "catalog" / "templates" / "mcp-server" / "kya-capability-mcp"
    required = {
        "artifact.manifest.json",
        "capability.manifest.json",
        "pyproject.toml",
        "sbom.cdx.json",
        "src/kya_capability_mcp/contracts.py",
        "src/kya_capability_mcp/server.py",
        "src/kya_capability_mcp/service.py",
        "tests/test_service.py",
    }
    present = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}

    assert required <= present
    manifest = json.loads((root / "artifact.manifest.json").read_text(encoding="utf-8"))
    capability = json.loads((root / "capability.manifest.json").read_text(encoding="utf-8"))
    assert manifest["type"] == "mcp-server"
    assert manifest["source"]["path"].startswith("catalog/sources/mcp-servers/")
    assert capability["entrypoints"]["server"] == "src/kya_capability_mcp/server.py"
