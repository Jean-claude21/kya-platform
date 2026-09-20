# KYA Native Document Runtime

## Objective

Provide a runtime-neutral, governed document model that lets KYA applications and authorized AI
assistants create business processes without deploying application code for every new form.

KYA-Platform remains the control plane. The future KYA Document Runtime executes published
document definitions and owns business records, workflow state, signatures and operational
projections.

## Boundary

The control plane owns identity context, organizational scope, OpenFGA authorization, catalog,
publication and global audit. The document runtime owns immutable document definitions, records,
workflow execution and derived operational views. Business applications such as KYA RH consume
both through the SDK and never become part of KYA-Core.

## Canonical package

Every document type release contains:

- `artifact.manifest.json` for ownership, provenance, integrity and governance;
- `document-type.json` for fields, references, workflow, privacy, signatures, notifications,
  views and metrics;
- optional examples and contract tests.

The initial publication route is the existing proposal flow: submission, deterministic admission,
Studio review, GitHub pull request, immutable signed release and scope assignment.

## First operational proofs

The first runtime proofs are generic operational forms: mission requests and equipment entry,
exit, transfer and return. They exercise governed references to people, clients, projects, sites
and inventory while preserving a permission-checked live identifier plus a bounded historical
snapshot. KYA RH remains a separate product slice whose survey and evaluation semantics will be
specified independently.

## Storage direction

PostgreSQL stores stable record metadata and versioned JSONB payloads. Configured indexes and
projections serve search and statistics. Binary attachments live in object storage and are bound by
digest. State transitions and signatures append evidence rather than rewriting history.
