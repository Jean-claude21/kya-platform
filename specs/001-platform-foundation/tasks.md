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

- [ ] T011 Write failing manifest contract tests in tests/contract/artifact-manifest.test.ts
- [ ] T012 Implement shared Zod contracts from contracts/ in packages/contracts/src/
- [ ] T013 [P] Configure Drizzle and migration runner in packages/db/
- [ ] T014 Create initial domain schemas and append-only audit migration in packages/db/migrations/
- [ ] T015 [P] Implement correlation, typed errors and redacted logs in packages/observability/src/
- [ ] T016 [P] Implement transaction, outbox and idempotency ports in packages/application/src/
- [ ] T017 [P] Implement Better Auth session boundary and OIDC identity mapping in packages/auth/src/
- [ ] T018 Write failing OpenFGA model tests for the KYA reference matrix in tests/policy/
- [ ] T019 Implement versioned OpenFGA model and authorization port in packages/authorization/
- [ ] T020 [P] Implement SecretReference port with no-value types in packages/secrets/src/
- [ ] T021 Create Hono API security middleware in apps/api/src/middleware/
- [ ] T022 Create TanStack application shell using the Design System package in apps/web/
- [ ] T023 Create worker runner with leases and retries in apps/worker/src/
- [ ] T024 Prove foundational checks locally and record results in specs/001-platform-foundation/evidence/foundation.md

## Phase 3 — US1: espaces et accès (P1, MVP)

- [ ] T025 [P] [US1] Write organization and workspace domain tests in packages/organization/test/
- [ ] T026 [P] [US1] Write negative authorization integration tests in tests/integration/workspace-access.test.ts
- [ ] T027 [US1] Implement units, relations, positions and dated assignments in packages/organization/src/
- [ ] T028 [US1] Implement workspaces, memberships, inheritance and explicit deny in packages/organization/src/workspaces/
- [ ] T029 [US1] Implement authorization explanation and filtered-list services in packages/authorization/src/
- [ ] T030 [US1] Add workspace and membership API routes in apps/api/src/routes/workspaces.ts
- [ ] T031 [US1] Build workspace switcher and access administration UI in apps/web/src/features/workspaces/
- [ ] T032 [US1] Execute Alice/Bob/Chloé/Sam matrix and record evidence in specs/001-platform-foundation/evidence/us1.md

## Phase 4 — US2: publication d'artefacts (P1)

- [ ] T033 [P] [US2] Write artifact lifecycle and separation-of-duty tests in packages/publication/test/
- [ ] T034 [P] [US2] Create official Skill, MCP, app and connector templates in catalog/templates/
- [ ] T035 [US2] Implement Artifact, ArtifactVersion and lifecycle rules in packages/catalog/src/
- [ ] T036 [US2] Implement submission, review, approval and immutable release in packages/publication/src/
- [ ] T037 [US2] Add publication API routes in apps/api/src/routes/publications.ts
- [ ] T038 [US2] Build artifact editor and approval inbox in apps/web/src/features/publication/
- [ ] T039 [US2] Publish one reference Skill end to end and record evidence in specs/001-platform-foundation/evidence/us2.md

## Phase 5 — US3: découverte, installation et mises à jour (P1)

- [ ] T040 [P] [US3] Write rights-filtered search and update-policy tests in packages/distribution/test/
- [ ] T041 [P] [US3] Write Registry MCP schema and authorization tests in tests/contract/registry-mcp.test.ts
- [ ] T042 [US3] Implement catalog search filtered before disclosure in packages/catalog/src/search/
- [ ] T043 [US3] Implement installation, compatibility, update and rollback services in packages/distribution/src/
- [ ] T044 [US3] Implement daily update assessment job in apps/worker/src/jobs/check-updates.ts
- [ ] T045 [US3] Implement OAuth-protected Registry MCP tools in apps/registry-mcp/src/
- [ ] T046 [US3] Build catalog, installation and update UI in apps/web/src/features/catalog/
- [ ] T047 [US3] Validate install-update-rollback through UI and MCP in specs/001-platform-foundation/evidence/us3.md

## Phase 6 — US4: systèmes et autorités (P2)

- [ ] T048 [P] [US4] Write unique-authority and conflict tests in packages/catalog/test/data-authority.test.ts
- [ ] T049 [US4] Implement systems, capabilities and temporal DataAuthority in packages/catalog/src/systems/
- [ ] T050 [US4] Implement Frappe registry adapter without data copying in packages/frappe-adapter/src/
- [ ] T051 [US4] Add system and authority API/UI in apps/api/src/routes/systems.ts and apps/web/src/features/systems/
- [ ] T052 [US4] Register Frappe pilot authority and record evidence in specs/001-platform-foundation/evidence/us4.md

## Phase 7 — US5: identités techniques et secrets (P2)

- [ ] T053 [P] [US5] Write scope, expiry, revocation and redaction tests in packages/secrets/test/
- [ ] T054 [US5] Implement Infisical machine-identity adapter in packages/secrets/src/infisical/
- [ ] T055 [US5] Implement secret-use request and approval service in packages/secrets/src/service.ts
- [ ] T056 [US5] Add secret metadata administration without reveal in apps/api/src/routes/secrets.ts and apps/web/src/features/secrets/
- [ ] T057 [US5] Validate preview-only secret expiry and emergency revocation in specs/001-platform-foundation/evidence/us5.md

## Phase 8 — US6: promotions Dokploy et Coolify (P2)

- [ ] T058 [P] [US6] Write DeploymentProvider conformance suite in packages/deployment/test/provider.contract.ts
- [ ] T059 [P] [US6] Implement Dokploy adapter in packages/deployment/src/dokploy/
- [ ] T060 [P] [US6] Implement Coolify adapter in packages/deployment/src/coolify/
- [ ] T061 [US6] Implement provider-neutral promotion and rollback service in packages/deployment/src/service.ts
- [ ] T062 [US6] Automate Neon preview branch create/cleanup in infra/neon/
- [ ] T063 [US6] Add preview, test and production workflows in .github/workflows/deploy.yml
- [ ] T064 [US6] Run identical provider benchmark and record decision in specs/001-platform-foundation/evidence/deployment-benchmark.md

## Phase 9 — US7: audit et administration (P3)

- [ ] T065 [P] [US7] Write audit immutability, redaction and scoped-query tests in packages/audit/test/
- [ ] T066 [US7] Implement append-only audit writer and query service in packages/audit/src/
- [ ] T067 [US7] Add auditor API with content separation in apps/api/src/routes/audit.ts
- [ ] T068 [US7] Build scoped audit timeline in apps/web/src/features/audit/
- [ ] T069 [US7] Reconstruct a complete artifact history in specs/001-platform-foundation/evidence/us7.md

## Phase 10 — Hardening and release

- [ ] T070 [P] Run dependency, secret, container and SBOM controls from .github/workflows/security.yml
- [ ] T071 [P] Validate accessibility and low-bandwidth journeys in tests/e2e/
- [ ] T072 [P] Add OpenTelemetry traces, metrics and health checks in packages/observability/
- [ ] T073 [P] Implement notification preferences, deduplication and delivery workers in packages/notifications/
- [ ] T074 [P] Prove identity deprovisioning revokes sessions and tokens in tests/security/deprovisioning.test.ts
- [ ] T075 [P] Implement artifact signing, verification and compromise revocation in packages/publication/src/integrity/
- [ ] T076 [P] Run catalog, authorization, API and MCP load tests from tests/performance/
- [ ] T077 Automate backup verification for Neon, OpenFGA and Infisical metadata in infra/backup/
- [ ] T078 Execute a restore and access-revocation recovery drill in specs/001-platform-foundation/evidence/disaster-recovery.md
- [ ] T079 Execute every quickstart criterion and complete specs/001-platform-foundation/evidence/final.md
- [ ] T080 Configure GitHub protections for main and dev after validating approver ownership in docs/governance/repository.md
- [ ] T081 Merge feat-platform-foundation to dev, create dev prerelease tag, and validate test deployment
- [ ] T082 Promote dev to main through PR and create the mandatory annotated SemVer release tag

## Dependencies and parallelism

Setup precedes Foundations. T024 unlocks the stories. US1 supplies the authorization context used by
US2–US7. After US1, US2 and US4 can proceed in parallel ; US5 and the provider adapters can proceed
against stable ports. US3 integrates US2 publication. US7 can start once audit events exist.

Suggested first demonstrable increment: T001–T032. It proves the organization, spaces and security
model before exposing publication or MCP write capabilities.
