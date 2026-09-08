# ADR 0005 — Expose Data Foundation through the single KYA MCP gateway

- **Status:** accepted
- **Date:** 2026-09-08

## Decision

Data capabilities register on the existing MCP server. OAuth grants distinct `data:read` and
`data:ingest` scopes; OpenFGA then decides in the active organizational unit. Handlers reuse
`DataService`, fail closed when audit is unavailable, and return projections without secrets or
storage locations.

## Consequences

- One connection is sufficient in Claude, ChatGPT or a compatible editor.
- Visible tools depend on consent, role and active context.
- Models receive neither arbitrary SQL nor provider keys.
- New scrapers integrate without changing governance contracts.
- Users can later configure a smaller personal tool profile without reconnecting the gateway.
