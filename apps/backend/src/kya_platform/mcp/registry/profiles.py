"""Authoritative registrations and initial KYA system profiles."""

from kya_platform.application.mcp_profiles import (
    SystemProfileRegistration,
    ToolRegistration,
)
from kya_platform.mcp.data.contracts import DATA_TOOLS
from kya_platform.mcp.registry.contracts import REGISTRY_TOOLS, RegistryTool


def _registration(tool: RegistryTool, namespace: str) -> ToolRegistration:
    return ToolRegistration(
        key=tool.name,
        namespace=namespace,
        display_name=tool.name.replace("_", " ").capitalize(),
        description=f"Capacité MCP gouvernée KYA : {tool.name}.",
        oauth_scope=tool.oauth_scope,
        target_object_type=tool.object_type,
        target_relation=tool.permission,
        risk=tool.risk.value,
        is_write=tool.is_write,
        requires_confirmation=tool.requires_confirmation,
        requires_idempotency=tool.requires_idempotency_key,
    )


TOOL_REGISTRATIONS = tuple(
    [
        *(_registration(tool, "registry") for tool in REGISTRY_TOOLS),
        *(_registration(tool, "data") for tool in DATA_TOOLS),
    ]
)

_REGISTRY_READ = tuple(tool.name for tool in REGISTRY_TOOLS if not tool.is_write)
_DATA_READ = tuple(tool.name for tool in DATA_TOOLS if not tool.is_write)
_DATA_OPERATOR = tuple(tool.name for tool in DATA_TOOLS)
_CATALOG_PUBLISHER = tuple(tool.name for tool in REGISTRY_TOOLS)

SYSTEM_PROFILES = (
    SystemProfileRegistration(
        "registry-reader",
        "Lecteur du registre",
        "Découvrir les artefacts, versions et opérations autorisés.",
        _REGISTRY_READ,
    ),
    SystemProfileRegistration(
        "data-reader",
        "Lecteur des données",
        "Découvrir, rechercher et citer les données autorisées.",
        _DATA_READ,
    ),
    SystemProfileRegistration(
        "data-operator",
        "Opérateur des données",
        "Lire les données et démarrer les ingestions autorisées.",
        _DATA_OPERATOR,
    ),
    SystemProfileRegistration(
        "catalog-publisher",
        "Opérateur du catalogue",
        "Lire, installer, mettre à jour et publier selon les autorisations métier.",
        _CATALOG_PUBLISHER,
    ),
)

__all__ = ["SYSTEM_PROFILES", "TOOL_REGISTRATIONS"]
