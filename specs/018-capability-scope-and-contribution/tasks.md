# Tasks — Capability scope and contribution v0.1

- [ ] Add `visibility_scope_unit_id` and `discoverable` migration to `catalog.artifact`.
- [ ] Add `catalog.proposal` table and migration.
- [ ] Extend `tests/policy/kya-platform.fga` with `can_propose` and scope-aware `artifact#can_view`.
- [ ] Implement `ProposalService` and `SqlAlchemyProposalRepository`.
- [ ] Implement `ScopePromotionService` reusing publication status machine.
- [ ] Implement the GitHub service-identity PR adapter (open PR, poll merge status).
- [ ] Implement `publish_candidate` against `ProposalService`; remove the `tool_not_implemented` stub.
- [ ] Add web Studio route(s) to list, review, approve or reject proposals.
- [ ] Extend catalog browse/detail to return the reduced discoverable-only shape.
- [ ] Add authorization-parity tests for discoverability without access.
- [ ] Add proposal-to-version integration test with a mocked GitHub adapter.
- [ ] Add promotion history-preservation test (version and installation history untouched).
- [ ] Run full quality gates.
