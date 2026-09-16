"""Validate and build the deterministic KYA-Platform Claude plugin archive."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "integrations" / "claude" / "kya-platform"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
EXPECTED_MCP_URL = "https://mcp.kya-platform.vttlife.com/registry/mcp"


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def files_under(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def validate() -> str:
    plugin = load_json(PLUGIN / ".claude-plugin" / "plugin.json")
    marketplace = load_json(MARKETPLACE)
    mcp = load_json(PLUGIN / ".mcp.json")

    version = plugin.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("plugin.json requires a non-empty version")
    if plugin.get("name") != "kya-platform":
        raise ValueError("plugin name must be kya-platform")

    entries = marketplace.get("plugins")
    if not isinstance(entries, list) or len(entries) != 1:
        raise ValueError("marketplace must expose exactly one KYA-Platform plugin")
    entry = entries[0]
    if not isinstance(entry, dict):
        raise ValueError("marketplace plugin entry must be an object")
    if entry.get("version") != version:
        raise ValueError("marketplace and plugin versions must match")
    if entry.get("source") != "./integrations/claude/kya-platform":
        raise ValueError("marketplace source must use the repository-relative plugin path")

    servers = mcp.get("mcpServers")
    if not isinstance(servers, dict):
        raise ValueError(".mcp.json requires mcpServers")
    server = servers.get("kya-platform")
    if not isinstance(server, dict) or server.get("url") != EXPECTED_MCP_URL:
        raise ValueError("KYA-Platform MCP URL is missing or unexpected")
    parsed = urlparse(EXPECTED_MCP_URL)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("KYA-Platform MCP must use an HTTPS URL")

    skill_root = PLUGIN / "skills" / "kya-design-system"
    manifest = load_json(skill_root / "artifact.manifest.json")
    if manifest.get("version") != version:
        raise ValueError("bundled skill and plugin versions must match")
    release = ROOT / "catalog" / "releases" / "kya-design-system" / f"{version}.zip"
    if not release.is_file():
        raise ValueError(f"published catalogue release is missing: {release}")

    actual = files_under(skill_root)
    with ZipFile(release) as archive:
        expected = {
            name: archive.read(name)
            for name in sorted(archive.namelist())
            if not name.endswith("/")
        }
    if actual.keys() != expected.keys():
        missing = sorted(expected.keys() - actual.keys())
        extra = sorted(actual.keys() - expected.keys())
        raise ValueError(f"bundled skill file set drifted; missing={missing}, extra={extra}")
    drifted = [name for name in expected if actual[name] != expected[name]]
    if drifted:
        raise ValueError(f"bundled skill content drifted from release {version}: {drifted}")

    forbidden_suffixes = {".pem", ".key", ".p12", ".pfx", ".env"}
    sensitive = [
        path.relative_to(PLUGIN).as_posix()
        for path in PLUGIN.rglob("*")
        if path.is_file() and path.suffix.lower() in forbidden_suffixes
    ]
    if sensitive:
        raise ValueError(f"sensitive files cannot be packaged: {sensitive}")
    return version


def build(output: Path, version: str) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(PLUGIN.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(PLUGIN).as_posix()
            info = ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"Built {output} (version {version}, sha256 {digest})")
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate without creating an archive")
    parser.add_argument("--output", type=Path, help="override the output zip path")
    args = parser.parse_args()
    version = validate()
    print(f"Validated KYA-Platform Claude plugin {version}")
    if args.check:
        return
    output = args.output or ROOT / "dist" / f"kya-platform-claude-plugin-{version}.zip"
    build(output, version)


if __name__ == "__main__":
    main()
