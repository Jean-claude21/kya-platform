# KYA Platform

KYA Platform is KYA-Energy Group's control plane for its digital assets. It registers, governs,
shares, publishes and audits systems, applications, APIs, data products, MCP servers and tools,
Skills, templates, models and company standards.

The project follows Spec-Driven Development with GitHub Spec Kit. The project constitution is the
normative source. Each feature then has a specification, implementation plan, tasks, consistency
checks and validation evidence before production.

## Repository map

- `apps/backend`: FastAPI modular monolith, MCP surfaces and workers.
- `apps/web`: TanStack user interface.
- `packages/design-system`: executable KYA UI foundations.
- `catalog/sources`: editable sources of real KYA artifacts.
- `catalog/templates`: governed master templates used to start new artifacts.
- `catalog/releases`: immutable, validated artifact releases.
- `docs`: maintained product, architecture, governance and operations documentation.
- `specs`: feature intent, plans, tasks and evidence.

## Branches

- `main`: stable, releasable versions.
- `dev`: integration of validated features.
- `feat-xxx`: isolated feature development, created from `dev` and merged into `dev` by Pull
  Request.
- Promotion from `dev` to `main` requires a Pull Request and release validation.

Every commit accepted on `main` receives an immutable annotated SemVer tag. Pre-release tags such
as `vX.Y.Z-dev.N` on `dev` are reserved for genuinely deployable milestones.

## Spec Kit

Expected workflow for each feature:

```text
constitution → specify → clarify → plan → tasks → analyze → implement → converge
```

Codex and Claude integrations live in the repository so agents use the same rules and artifacts.

## Documentation

English is the canonical documentation language. Run `pnpm docs:serve` for local preview and
`pnpm docs:build` for the same strict build enforced in CI.

## Current status

The platform foundations are operational and continue to be expanded through validated vertical
slices. A capability is complete only when its code, tests, documentation and real-use evidence
agree.
