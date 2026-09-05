# Tasks: Fondation de KYA Platform

**Input**: `specs/001-platform-foundation/`  
**Rule**: tests first for domain rules, authorization, contracts, migrations and integrations.

## Phase 1 — Setup

- [x] T001 Create pnpm workspace and root scripts in package.json and pnpm-workspace.yaml
- [x] T002 Create Turborepo task graph in turbo.json
- [x] T003 [P] Configure TypeScript strict shared settings in packages/config-typescript/
- [x] T004 [P] Configure ESLint, formatting and import boundaries in packages/config-eslint/
- [x] T005 [P] Configure Vitest and Playwright shared settings in packages/test-kit/
- [x] T006 Create app and package directories from plan.md with minimal package manifests
- [x] T007 [P] Add secret-safe environment validation in packages/config/src/env.ts and .env.example
- [x] T008 [P] Add container build and local compose skeleton in infra/containers/
- [x] T009 Add GitHub CI checks for feat-xxx to dev and dev to main in .github/workflows/ci.yml
- [x] T010 Add SemVer tag verification and immutable artifact workflow in .github/workflows/release.yml

## Phase 2 — Foundational blockers

- [x] T011 Configure uv, Python 3.14, FastAPI app factory, lifespan, health routes and pytest in apps/backend/
- [x] T012 Write failing manifest contract tests in apps/backend/tests/contract/test_artifact_manifest.py
- [x] T013 Implement shared Pydantic contracts and export OpenAPI/JSON Schema in apps/backend/src/kya_platform/contracts/
- [x] T014 [P] Configure async SQLAlchemy 2, Alembic and the initial domain/audit migration in apps/backend/
- [x] T015 [P] Implement correlation, typed errors and redacted logs in apps/backend/src/kya_platform/observability/
- [x] T016 [P] Implement transaction, outbox and idempotency ports in apps/backend/src/kya_platform/application/
- [x] T017 [P] Implement FastAPI Neon Auth JWT/JWKS validation and immutable issuer/subject mapping
- [x] T018 Write failing OpenFGA model tests for the KYA reference matrix in tests/policy/
- [x] T019 Implement versioned OpenFGA model and authorization port in apps/backend/src/kya_platform/authorization/
- [x] T020 [P] Implement SecretReference port with no-value types in apps/backend/src/kya_platform/secrets/
- [x] T021 Create FastAPI security middleware and dependency guards in apps/backend/src/kya_platform/api/
- [x] T022 Create TanStack application shell using the Design System package in apps/web/
- [x] T023 Create Python worker runner with leases and retries in apps/backend/src/kya_platform/workers/
- [x] T024 Prove foundational checks locally and record results in specs/001-platform-foundation/evidence/foundation.md

## Phase 3 — US1: espaces et accès (P1, MVP)

- [x] T025 [P] [US1] Write organization and workspace domain tests in apps/backend/tests/domain/
- [x] T026 [P] [US1] Write negative authorization integration tests in apps/backend/tests/integration/test_workspace_access.py
- [x] T027 [US1] Implement units, relations, positions and dated assignments in apps/backend/src/kya_platform/domain/organization/
- [x] T028 [US1] Implement workspaces, memberships, inheritance and explicit deny in apps/backend/src/kya_platform/domain/workspaces/
- [x] T029 [US1] Implement authorization explanation and filtered-list services in apps/backend/src/kya_platform/authorization/
- [x] T030 [US1] Add workspace and membership API routes in apps/backend/src/kya_platform/api/routes/workspaces.py
- [x] T031 [US1] Build workspace switcher and access administration UI in apps/web/src/features/workspaces/
- [x] T032 [US1] Execute Alice/Bob/Chloé/Sam matrix and record evidence in specs/001-platform-foundation/evidence/us1.md

## Phase 4 — US2: publication d'artefacts (P1)

- [x] T033 [P] [US2] Write artifact lifecycle and separation-of-duty tests in apps/backend/tests/domain/
- [x] T034 [P] [US2] Create official Skill, MCP, app and connector templates in catalog/templates/
- [x] T035 [US2] Implement Artifact, ArtifactVersion and lifecycle rules in apps/backend/src/kya_platform/domain/catalog/
- [x] T036 [US2] Implement submission, review, approval and immutable release in apps/backend/src/kya_platform/application/publication/
- [x] T037 [US2] Add publication API routes in apps/backend/src/kya_platform/api/routes/publications.py
- [x] T038 [US2] Build artifact editor and approval inbox in apps/web/src/features/publication/
- [x] T039 [US2] Publish one reference Skill end to end and record evidence in specs/001-platform-foundation/evidence/us2.md

## Phase 5 — US3: découverte, installation et mises à jour (P1)

- [x] T040 [P] [US3] Write rights-filtered search and update-policy tests in apps/backend/tests/domain/
- [x] T041 [P] [US3] Write Registry MCP schema and authorization tests in apps/backend/tests/contract/test_registry_mcp.py
- [x] T042 [US3] Implement catalog search filtered before disclosure in apps/backend/src/kya_platform/application/catalog/
- [x] T043 [US3] Implement installation, compatibility, update and rollback services in apps/backend/src/kya_platform/application/distribution/
- [x] T044 [US3] Implement daily update assessment job in apps/backend/src/kya_platform/workers/check_updates.py
- [x] T045 [US3] Implement OAuth-protected Registry MCP tools in apps/backend/src/kya_platform/mcp/
- [x] T046 [US3] Build catalog, installation and update UI in apps/web/src/features/catalog/
- [ ] T047 [US3] Validate install-update-rollback through UI and MCP in specs/001-platform-foundation/evidence/us3.md

## Phase 6 — US4: systèmes et autorités (P2)

- [x] T048 [P] [US4] Write unique-authority and conflict tests in apps/backend/tests/domain/test_data_authority.py
- [x] T049 [US4] Implement systems, capabilities and temporal DataAuthority in apps/backend/src/kya_platform/domain/systems/
- [x] T050 [US4] Implement Frappe registry adapter without data copying in apps/backend/src/kya_platform/infrastructure/frappe/
- [x] T051 [US4] Add system and authority API/UI in apps/backend/src/kya_platform/api/routes/systems.py and apps/web/src/features/systems/
- [x] T052 [US4] Register KYA Platform as the first factual authority and record evidence in specs/001-platform-foundation/evidence/us4.md; defer Frappe to its own validated pilot

## Phase 7 — US5: identités techniques et secrets (P2)

- [x] T053 [P] [US5] Write scope, expiry, revocation and redaction tests in apps/backend/tests/security/
- [x] T054 [US5] Implement Infisical machine-identity adapter in apps/backend/src/kya_platform/infrastructure/infisical/
- [x] T055 [US5] Implement secret-use request and approval service in apps/backend/src/kya_platform/application/secrets/
- [x] T056 [US5] Add secret metadata administration without reveal in apps/backend/src/kya_platform/api/routes/secrets.py and apps/web/src/features/secrets/
- [x] T057 [US5] Validate preview-only secret expiry and emergency revocation in specs/001-platform-foundation/evidence/us5.md

## Phase 8 — US6: promotions Dokploy et Coolify (P2)

- [x] T058 [P] [US6] Write DeploymentProvider conformance suite in apps/backend/tests/contract/test_deployment_provider.py
- [x] T059 [P] [US6] Implement Dokploy adapter in apps/backend/src/kya_platform/infrastructure/dokploy/
- [x] T060 [P] [US6] Implement Coolify adapter in apps/backend/src/kya_platform/infrastructure/coolify/
- [x] T061 [US6] Implement provider-neutral promotion and rollback service in apps/backend/src/kya_platform/application/deployment/
- [x] T062 [US6] Automate Neon preview branch create/cleanup in infra/neon/
- [x] T063 [US6] Add preview, test and production workflows in .github/workflows/deploy.yml
- [ ] T064 [US6] Run identical provider benchmark and record decision in specs/001-platform-foundation/evidence/deployment-benchmark.md

## Phase 9 — US7: audit et administration (P3)

- [x] T065 [P] [US7] Write audit immutability, redaction and scoped-query tests in apps/backend/tests/domain/test_audit.py
- [x] T066 [US7] Implement append-only audit writer and query service in apps/backend/src/kya_platform/application/audit/
- [x] T067 [US7] Add auditor API with content separation in apps/backend/src/kya_platform/api/routes/audit.py
- [x] T068 [US7] Build scoped audit timeline in apps/web/src/features/audit/
- [x] T069 [US7] Reconstruct a complete artifact history in specs/001-platform-foundation/evidence/us7.md

## Phase 10 — Hardening and release

- [x] T070 [P] Run dependency, secret, container and SBOM controls from .github/workflows/security.yml
- [x] T071 [P] Validate accessibility and low-bandwidth journeys in tests/e2e/
- [x] T072 [P] Add OpenTelemetry traces, metrics and health checks in apps/backend/src/kya_platform/observability/
- [x] T073 [P] Implement notification preferences, deduplication and delivery workers in apps/backend/src/kya_platform/workers/
- [x] T074 [P] Prove identity deprovisioning revokes sessions and tokens in apps/backend/tests/security/test_deprovisioning.py
- [x] T075 [P] Implement artifact signing, verification and compromise revocation in apps/backend/src/kya_platform/application/publication/integrity/
- [x] T076 [P] Run catalog, authorization, API and MCP load tests from tests/performance/
- [x] T077 Automate backup verification for Neon, OpenFGA and Infisical metadata in infra/backup/
- [ ] T078 Execute a restore and access-revocation recovery drill in specs/001-platform-foundation/evidence/disaster-recovery.md
- [ ] T079 Execute every quickstart criterion and complete specs/001-platform-foundation/evidence/final.md
- [ ] T080 Configure GitHub protections for main and dev after validating approver ownership in docs/governance/repository.md
- [x] T081 Merge feat-platform-foundation to dev, create dev prerelease tag, and validate test deployment
- [ ] T082 Promote dev to main through PR and create the mandatory annotated SemVer release tag
- [x] T083 [US7] Implement and test autonomous one-time platform-owner initialization and canonical
  MCP URLs in apps/backend/ and apps/web/

## Dependencies and parallelism

Setup precedes Foundations. T024 unlocks the stories. US1 supplies the authorization context used by
US2–US7. After US1, US2 and US4 can proceed in parallel ; US5 and the provider adapters can proceed
against stable ports. US3 integrates US2 publication. US7 can start once audit events exist.

Suggested first demonstrable increment: T001–T032. It proves the organization, spaces and security
model before exposing publication or MCP write capabilities.
