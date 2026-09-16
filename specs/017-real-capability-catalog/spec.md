# Specification — Real governed capability catalog v0.1

**Branch**: `feat-real-capability-catalog`  
**Date**: 2026-09-10  
**Status**: implementation

## Goal

Replace the illustrative web catalog with the same authorized, Neon-backed artifact catalog used by
KYA-Platform's Registry MCP, while preserving explicit consent for installation and all sensitive
distribution operations.

## User stories

### US1 — Browse only authorized capabilities (P1)

An authenticated user opens the catalog and sees published capabilities that are viewable in their
active organizational unit. Hidden identifiers must not leak through results, counts or errors.

### US2 — Inspect a real immutable release (P1)

Selecting a result shows its stable KYA identifier, type, latest published version, available
versions, installability and integrity status from Neon.

### US3 — Search and filter without changing the security boundary (P1)

Text and type filters are applied only after OpenFGA has produced the caller's allowed artifact
identifiers. Empty text means browse; it never means bypass authorization.

### US4 — Request governed distribution actions (P2)

An authorized user can request an installation, compatible update or rollback plan. The server
returns an immutable plan; a supported client performs local writes only after explicit consent and
returns a receipt.

## Functional requirements

- **FR-001** — HTTP and MCP discovery use one application-level query service and contracts.
- **FR-002** — Every query is scoped to the authenticated principal and active unit.
- **FR-003** — OpenFGA filtering occurs before any search-index or database text search.
- **FR-004** — Browsing supports an empty query, type filters and a bounded result limit.
- **FR-005** — Responses contain no storage credentials, internal database IDs or hidden counts.
- **FR-006** — Details expose only published or otherwise explicitly viewable versions.
- **FR-007** — Installation, update and rollback reuse existing integrity, compatibility,
  idempotency, audit and confirmation rules.
- **FR-008** — The web screen renders loading, empty, error and ready states without demo data.
- **FR-009** — The approved KYA Signature design remains responsive and keyboard accessible.

## Success criteria

- The web catalog and `search_catalog` MCP tool return the same authorized capability set.
- A principal without `can_view` sees an empty list and no artifact identifiers.
- A published KYA Design System Skill can be discovered and inspected from the web catalog.
- No browser-side constant is used as a catalog item or installation state.
