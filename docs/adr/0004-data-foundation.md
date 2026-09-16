# ADR 0004 — Separate data control, content and execution

- **Status:** accepted
- **Date:** 2026-09-07

## Decision

KYA Data Foundation stores sources, assets, contracts, pipelines, runs, quality evidence and lineage
in Neon PostgreSQL. Large content is stored as immutable objects; PostgreSQL stores its reference
and digest.

Connectors are governed catalog artifacts. Every pipeline pins an exact connector version. Secret
identifiers are opaque and their values remain in Infisical.

## Rationale

This separation makes acquisition replayable and auditable, avoids a dedicated interface for every
need, and allows applications and AI environments to use the same reliable data. It also supports a
progressive transition away from Frappe without abruptly migrating existing workflows.

## Consequences

- Scraping is a connector family, not a generic Web route.
- AI does not own deterministic guarantees.
- Every published dataset has a contract, provenance and quality evidence.
- Replacing storage or a source system does not change asset identity.
