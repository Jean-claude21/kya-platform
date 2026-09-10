# Specification — Real AI environments v0.1

**Branch**: `feat-real-ai-environments`  
**Date**: 2026-09-10  
**Status**: implementation

## Goal

Replace the AI environment screen's assumed connector identifiers with the authenticated user's
actual active MCP OAuth connections and their effective governed tool profiles.

## User stories

### US1 — See real AI connections (P1)

An authenticated user sees only live MCP connections belonging to their identity and active unit,
with the registered client name, granted scopes, connection time and refresh expiry.

### US2 — Inspect the effective tool surface (P1)

Selecting a connection loads the effective tool set calculated from its real client identifier,
OAuth scopes, active unit, authorization graph, applicable profiles and restrictive preferences.

### US3 — Recover from empty and unavailable states (P1)

The screen distinguishes no active connection from an unavailable service and offers a retry action
without inventing sample connections or capabilities.

## Functional requirements

- **FR-001** — Discover active connectors from non-revoked, non-expired refresh-token records.
- **FR-002** — Return at most one, latest connection per OAuth client.
- **FR-003** — Never return tokens, client secrets, redirect URIs or sensitive authorization evidence.
- **FR-004** — Scope discovery to the authenticated principal and active unit.
- **FR-005** — Use the discovered `client_id` for effective-profile resolution.
- **FR-006** — Render explicit loading, empty, error and ready states.
- **FR-007** — Keep the approved KYA Signature visual language and responsive behavior.

## Success criteria

- No hard-coded AI connector identifiers remain in the screen.
- A live Claude or ChatGPT MCP authorization appears under its registered client name.
- Disconnecting, revoking or expiring the refresh grant removes it from the next read.
- Backend contract tests and frontend unit tests cover ready, empty and failure behavior.
