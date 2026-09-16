# ADR 0002 — Branchable Neon Auth and Object Storage

- **Status:** accepted
- **Date:** 2026-09-03
- **Decision owner:** KYA-Energy Group CVSI

## Decision

Neon provides KYA Platform's branchable foundation: Postgres, Neon Auth and Object Storage. Each
preview receives isolated data, identity and files. FastAPI remains the single business trust
boundary and does not delegate authorization decisions to the interface.

Neon Auth authenticates people and issues tokens. FastAPI validates issuer, audience, JWKS
signature and expiration. OpenFGA then decides whether the principal may act on the resource in the
active scope.

Neon Object Storage implements a replaceable S3 port. It stores files and bundles, never source
code, authorization metadata or secret values. While the service is in beta, critical objects keep
an independent copy and restore strategy.

## Consequences

- KYA Platform does not install Better Auth directly.
- Preview identities follow Neon branches.
- TanStack receives no PostgreSQL connection.
- The Data API is not a parallel business path around FastAPI.
- Object Storage keys remain in Infisical and never enter the catalog.
