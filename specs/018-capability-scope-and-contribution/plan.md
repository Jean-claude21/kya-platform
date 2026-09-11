# Plan — Capability scope and contribution v0.1

1. Data model: add `visibility_scope_unit_id` and `discoverable` to `catalog.artifact`; add the
   `catalog.proposal` table (author, target artifact or new-Skill workspace, package payload,
   status, linked pull request URL, linked commit SHA once merged).
2. Authorization: extend the FGA model with `workspace#can_propose` (broader than `can_edit`) and
   redefine `artifact#can_view` to check `visibility_scope_unit_id` membership in addition to the
   owning workspace's own `can_view`. Add `artifact#discoverable` as a metadata-only flag, not an
   FGA relation, enforced in the application query layer (FR-006/FR-007).
3. Application services: `ProposalService` (create, list for reviewer, approve, reject) and
   `ScopePromotionService` (reusing `CatalogPublicationRequest` plumbing) behind ports, mirroring
   the existing `ArtifactRegistryService` / publication service split.
4. GitHub integration: a narrow adapter that opens a PR from a service identity, polls or receives a
   webhook for merge status, and exposes only `open_pull_request` / `get_pull_request_status` to the
   application layer. No standing merge rights for the service identity.
5. Implement `publish_candidate` (Registry MCP) against `ProposalService`, replacing the
   `tool_not_implemented` stub. Add matching web routes so the Studio can also create proposals.
6. Extend catalog browse/detail services to return the reduced discoverable-only shape for callers
   without `can_view`, per FR-006/FR-007, reusing `017-real-capability-catalog`'s service split.
7. Tests: authorization-parity tests for discoverability without access, proposal-to-version
   integration test with a mocked GitHub adapter, and promotion history-preservation test.
