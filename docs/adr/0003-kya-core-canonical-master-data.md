# ADR 0003 — KYA Core as an independent canonical registry

- **Status:** accepted
- **Date:** 2026-09-07

## Context

KYA applications must share a changing organization, people, customers, projects and sites without
reproducing scattered duplicates and customizations. Frappe and ERPNext remain useful during the
transition, but they must not define the identifiers or structure of new autonomous applications.

## Decision

KYA Core is a domain of the FastAPI modular monolith. Neon stores its canonical data in the `core`
schema. Consumers use its application ports and Business API; future MCP capabilities and Frappe
adapters will use the same use cases.

The model distinguishes:

- a `Party`, which is a business entity, from a `Principal`, which is a digital identity;
- a stable person from dated work relationships and dated position assignments;
- stable organizational units from extensible types and historical relationships;
- customers, projects and sites owned by an explicit organizational scope.

OpenFGA decides access. Neon guarantees constraints. The transactional outbox publishes changes in
the same transaction. The migration creates the `group` root unit, while secured bootstrap grants
ownership: reference data and privileges are not conflated.

## Rejected options

- Keep Frappe DocTypes as the sole authority: this preserves tight coupling and existing duplicates.
- Extract KYA Core immediately as a microservice: this adds operational cost without an independent
  load or release requirement.
- Design a complete interface first: this would freeze screens before contracts and real use cases.

## Consequences

- An application can start without Frappe and receive an adapter later.
- Keys and relationships have an auditable history and explicit authority.
- Version 0.1 exposes only units, customers and projects; contacts, people, positions, sites and work
  relationships open through justified vertical slices.
- Every schema change uses a reversible migration tested on an isolated Neon branch.

## Review condition

Reconsider extraction when KYA Core has a genuinely independent owner, security level, load profile
or release lifecycle.
