# Tasks — Capability scope and contribution v0.1

- [x] Add `visibility_scope_unit_id` and `discoverable` migration to `catalog.artifact`.
- [x] Add `catalog.proposal` table and migration.
- [x] Extend `tests/policy/kya-platform.fga` with `can_propose` and scope-aware `artifact#can_view`.
- [x] Implement `ProposalService` and `SqlAlchemyProposalRepository`.
- [x] Implement `ScopePromotionService` reusing publication status machine.
- [x] Implement the GitHub service-identity PR adapter (open PR, poll merge status).
- [x] Implement `publish_candidate` against `PublicationService` (Git-backed publication flow);
      remove the `tool_not_implemented` stub. A separate non-Git-backed proposal MCP tool remains a
      future increment if MCP-originated proposals (as opposed to HTTP) are needed.
- [ ] Add web Studio route(s) to list, review, approve or reject proposals.
- [x] Extend catalog browse/detail to return the reduced discoverable-only shape.
  - [x] Add authorization-parity tests for discoverability without access.
- [x] Add proposal-to-version integration test with a mocked GitHub adapter.
- [x] Add promotion history-preservation test (version and installation history untouched; the
      artifact row's identity, versions and installations are never duplicated by a promotion).
- [ ] Run full quality gates.

## Additional completed work beyond the original checklist

- [x] HTTP routes for the full proposal lifecycle: create, approve, reject, open pull request,
      poll merge status, get status (`api/routes/proposals.py`).
- [x] GitHub App configuration wired end-to-end in `Settings` and `main.py`, active only when
      fully configured (fail-closed to 503, matching every other optional integration in this codebase).
- [x] GitHub App private key stored base64-encoded to satisfy Coolify's build-arg injection
      constraint (a raw multi-line PEM breaks Dockerfile ARG syntax).
- [x] Debian security upgrades applied to `Dockerfile.backend` and `Dockerfile.source-scheduler`
      runtime stages (unrelated CVEs surfaced by Trivy after the base image's package index updated).
- [x] `ScopePromotionRequest` domain model, `ScopePromotionService` application layer,
      `SqlAlchemyScopePromotionRepository`, and HTTP routes (`api/routes/scope_promotions.py`) for
      the full submit/review/approve/apply lifecycle.
- [x] New OpenFGA `org_unit#ancestor` relation (`parent or ancestor from parent`), used to verify a
      promotion target unit is a real ancestor of the artifact's current scope before accepting the
      request — never a same-rank or unrelated unit.
- [x] Applying a promotion widens `catalog.artifact.visibility_scope_unit_id` in place; the artifact
      row, its versions and installations are never duplicated or reset by a promotion.
