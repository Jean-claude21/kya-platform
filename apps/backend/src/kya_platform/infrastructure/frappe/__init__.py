"""Frappe registry adapter: metadata and references, never business-row copies."""

from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from kya_platform.contracts.artifact_manifest import RiskLevel
from kya_platform.domain.organization import DateRange
from kya_platform.domain.systems import (
    ApprovedInterface,
    AvailabilityLevel,
    DataAuthority,
    InterfaceKind,
    RegisteredSystem,
    SystemCapability,
    SystemRegistry,
    SystemStatus,
)


@dataclass(frozen=True, slots=True)
class FrappeAuthorityDeclaration:
    id: UUID
    category_key: str
    scope: str
    validity: DateRange


@dataclass(frozen=True, slots=True)
class FrappeRegistryAdapter:
    """Describe where Frappe data lives without moving that data into the Hub."""

    system_id: UUID
    base_url: str
    business_owner: str
    technical_owner: str = "CVSI"

    def __post_init__(self) -> None:
        normalized = self.base_url.rstrip("/")
        parsed = urlsplit(normalized)
        is_local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Frappe base URL must be an absolute HTTP URL")
        if parsed.scheme != "https" and not is_local:
            raise ValueError("Frappe integration requires HTTPS outside local development")
        object.__setattr__(self, "base_url", normalized)

    def registry(self, declarations: tuple[FrappeAuthorityDeclaration, ...]) -> SystemRegistry:
        system = RegisteredSystem(
            id=self.system_id,
            key="frappe-erpnext",
            name="Frappe / ERPNext",
            business_owner=self.business_owner,
            technical_owner=self.technical_owner,
            status=SystemStatus.ACTIVE,
            environments=frozenset({"production"}),
            interfaces=(
                ApprovedInterface(
                    name="REST API Frappe",
                    kind=InterfaceKind.REST_API,
                    contract_uri=f"{self.base_url}/api/resource",
                    approved=True,
                ),
            ),
            availability=AvailabilityLevel.BUSINESS_HOURS,
        )
        capabilities = tuple(
            SystemCapability(
                key=f"{declaration.category_key}-read",
                name=f"Lire {declaration.category_key} dans le système autoritaire",
                provider_system_id=self.system_id,
                contract_uri=(
                    f"{self.base_url}/api/resource/"
                    f"{{doctype}}?fields=[%22name%22]&limit_page_length={{limit}}"
                ),
                risk=RiskLevel.READ,
            )
            for declaration in declarations
        )
        authorities = tuple(
            DataAuthority(
                id=declaration.id,
                category_key=declaration.category_key,
                system_id=self.system_id,
                scope=declaration.scope,
                validity=declaration.validity,
            )
            for declaration in declarations
        )
        return SystemRegistry((system,), capabilities, authorities)


__all__ = ["FrappeAuthorityDeclaration", "FrappeRegistryAdapter"]
