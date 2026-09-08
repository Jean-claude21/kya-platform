"""Protect the modular monolith dependency direction from accidental erosion."""

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parents[2] / "src" / "kya_platform"


def _kya_import_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        for name in names:
            prefix = "kya_platform."
            if name.startswith(prefix):
                roots.add(name.removeprefix(prefix).split(".", maxsplit=1)[0])
    return roots


def _violations(layer: str, forbidden: set[str]) -> list[str]:
    violations: list[str] = []
    for path in sorted((PACKAGE_ROOT / layer).rglob("*.py")):
        imported = _kya_import_roots(path) & forbidden
        if imported:
            relative = path.relative_to(PACKAGE_ROOT).as_posix()
            violations.append(f"{relative}: {', '.join(sorted(imported))}")
    return violations


def test_domain_depends_only_on_domain_and_contracts() -> None:
    allowed = {"domain", "contracts"}
    all_layers = {path.name for path in PACKAGE_ROOT.iterdir() if path.is_dir()}

    assert _violations("domain", all_layers - allowed) == []


def test_application_does_not_depend_on_delivery_or_infrastructure() -> None:
    forbidden = {"api", "infrastructure", "mcp", "workers"}

    assert _violations("application", forbidden) == []
