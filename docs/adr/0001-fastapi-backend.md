# ADR 0001 — FastAPI as the single business backend

- **Status:** accepted
- **Date:** 2026-09-03
- **Decision owner:** KYA-Energy Group CVSI

## Context

The platform must protect Neon, secrets, fine-grained authorization, audit, publications, MCP tools
and deployments. A TanStack interface alone is not a sufficient trust boundary. Maintaining
parallel TypeScript and Python business APIs would create two implementations of the same rules.

## Decision

FastAPI is the single business backend. The same Python package exposes three logical processes:

1. a versioned HTTP API;
2. a protected MCP registry and gateway;
3. workers and scheduled routines.

TanStack owns the user experience and integrates Neon Auth. FastAPI validates Neon Auth token
issuer, audience, JWKS signature and expiration, then asks OpenFGA for authorization decisions.
SQLAlchemy 2 and Alembic are the single persistence path to Neon.

## Consequences

- Provider keys and Neon connections never reach the browser.
- Business rules are tested once with pytest.
- API, MCP and workers may deploy separately without becoming independent microservices.
- Web contracts derive from OpenAPI and JSON Schema.
- Hono and Drizzle do not carry business logic or migrations.

## Guardrails

- Dependencies point `delivery → application → domain`.
- Provider adapters implement application-facing ports.
- Every action is denied by default and checked by OpenFGA at execution time.
- Published migrations are immutable.
- Contract, policy, security and integration tests run before promotion.
