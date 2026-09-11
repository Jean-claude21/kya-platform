# Specification — Capability scope and contribution v0.1

**Branch**: `feat-capability-scope-and-contribution`
**Date**: 2026-09-11
**Status**: ready for implementation

## Goal

Let every user create and improve capabilities (Skills, MCP tools, apps) inside their own personal
or team workspace, discover similar capabilities already built elsewhere before duplicating work,
and let a governed decision promote a proven capability's visibility up to the whole company,
without ever duplicating the artifact or weakening the existing publication chain of custody.

This specification extends `002-artifact-registry` and `013-skill-factory`. It does not replace any
existing rule; it adds the scope-growth lifecycle and the non-developer contribution path left open
by those specs.

## Background — decisions carried into this spec

- Git remains the source of truth for published artifact content (`002-artifact-registry` FR-015).
  This spec does not change that. It adds a proposal stage that exists in Neon only, before any Git
  commit is required, so a non-developer can contribute without knowing Git.
- `publish_candidate` (Registry MCP tool, `catalog:publish` scope) is defined in contracts but
  returns `tool_not_implemented`. This spec defines what it must do instead of leaving it a stub.
- Ownership (`business_owner_id`, `technical_owner_id`) and authorship (`requested_by`) stay
  distinct on purpose; authorship never auto-grants ownership.

## User stories

### US1 — Work in a personal or team space first (P1)

A user creates or improves a Skill inside their personal workspace, or a team workspace shared with
named collaborators. Nobody outside that workspace can see or install it unless explicitly invited
as a member, or unless the artifact is later promoted (US4).

**Independent test**: two users in different personal workspaces cannot see each other's
in-progress Skills through browse, search, or the Registry MCP `search_catalog` tool.

### US2 — Discover similar work before duplicating it (P1)

Before building a new Skill, a user can discover that a similar capability already exists in
another workspace, even one they cannot install, provided its owner allowed discovery. The result
shows only non-sensitive descriptive metadata (name, summary, artifact type, owning workspace name)
and never file contents, internals, or an install path.

**Independent test**: a discoverable personal-workspace artifact appears in search results for a
user without `can_view` on it, with a distinct "not installable, contact owner" state; a
non-discoverable one never appears.

### US3 — Propose a new Skill or an improvement without using Git (P1)

A user working from Claude, ChatGPT or Codex, connected through the Registry MCP, submits a new
Skill or an improved version of an existing one they do not own. This creates a proposal, not an
`artifact_version`; no Git commit is required at this step.

**Independent test**: `publish_candidate` invoked by a user without a Git identity produces a
reviewable proposal visible to the target artifact's owners (or, for a new Skill, to the workspace's
reviewers), with the submitter recorded only as author.

### US4 — Promote a proven capability to a wider scope, including company-wide (P1)

An owner or a governance role reviews usage evidence (active installations, no rollback, age) for an
artifact and requests a scope promotion: personal to team, team to direction, direction to group
(company-wide). This reuses the existing publication approval chain; it never creates a duplicate
artifact.

**Independent test**: promoting an artifact's visibility scope does not change its
`owner_workspace_id`, preserves its full version history, and immediately changes what
`list_authorized_objects` returns for users outside the original workspace.

### US5 — A proposal becomes a real, auditable Git version only once approved (P1)

Once a reviewer approves a proposal, the system opens a pull request on behalf of a dedicated
service account against the artifact's repository, with the reviewer as the required GitHub
approver. Only after that PR merges does the proposal turn into a real `artifact_version` with a
genuine commit SHA, eligible for the existing `002-artifact-registry` publication cycle.

**Independent test**: no `artifact_version` row is ever created from a proposal without a merged
PR; the recorded commit SHA on the resulting version matches the merge commit.

## Functional requirements

### Scope model

- **FR-001** — An artifact MUST keep a single stable `owner_workspace_id` for accountability, set
  once at draft creation and never silently changed.
- **FR-002** — An artifact MUST carry a separate `visibility_scope_unit_id` referencing the
  organizational unit up to which it is visible (e.g. a direction, a country, the group root). It
  starts equal to the owning workspace's linked unit and only ever widens.
- **FR-003** — `can_view` on an artifact MUST be derived from `visibility_scope_unit_id` using the
  same unit-hierarchy membership check already used for `org_unit#member`/`administrator`, not a
  separate ad hoc rule.
- **FR-004** — Narrowing a scope (removing group-wide visibility) MUST be a distinct governed action
  (suspension), never an automatic reversal of a promotion.
- **FR-005** — Promotion MUST reuse `CatalogPublicationRequest`'s status machine and separation of
  duties; a promotion request is a release with an unchanged content digest and a widened scope.

### Discoverability without access

- **FR-006** — A workspace owner MAY mark an artifact `discoverable` independently of its
  `visibility_scope_unit_id`. Discoverable artifacts appear in search with a reduced field set
  (name, summary, artifact type, owning workspace display name) and an explicit `installable: false`
  marker to any caller without `can_view`.
- **FR-007** — Discovery results for non-authorized callers MUST NOT include file contents,
  manifests, versions, digests, or an installation path.
- **FR-008** — `discoverable` defaults to `false` for `personal` workspaces and `true` for `team`
  and wider workspaces; the owner can change it at any time without a governance cycle, since it
  grants visibility, not access.

### Contribution without Git

- **FR-009** — A new `catalog.proposal` entity MUST hold submitted content (files, inferred
  manifest fields) without requiring a Git commit, `source.commit`, or `content_digest` verified
  against a repository.
- **FR-010** — Every proposal MUST pass the existing `ArtifactArchiveValidator` checks (secrets,
  path safety, size, compression ratio) before becoming visible to any reviewer, regardless of
  submission channel (web Studio or MCP).
- **FR-011** — A proposal MUST record `requested_by` (author) only; it MUST NOT set
  `business_owner_id` or `technical_owner_id`. For a brand-new Skill with no existing owner, these
  fields are assigned by the reviewer at approval time, not inferred from the author.
- **FR-012** — `can_propose` on `workspace` MUST be a distinct, broader OpenFGA relation than
  `can_submit` on `artifact`; any active member of a workspace MAY open a proposal against artifacts
  visible to them, or against their own workspace for a brand-new Skill.
- **FR-013** — `publish_candidate` MUST create or update a `catalog.proposal`, never an
  `artifact_version`, and MUST return its proposal id and status.
- **FR-014** — Approving a proposal MUST open a pull request via a dedicated service identity
  against the artifact's declared repository; the human reviewer becomes the required GitHub
  approver. The service identity MUST NOT hold standing merge rights; merge happens through the
  approver's own action.
- **FR-015** — A `catalog.proposal` MUST transition to an `artifact_version` (entering the existing
  `002-artifact-registry` cycle) only after its linked pull request reports a merged state with a
  commit SHA, fetched and verified server-side, never trusted from client input.
- **FR-016** — Each user MAY have at most a configurable number (default 5) of proposals awaiting
  review at once; exceeding it MUST fail closed with a clear, non-punitive message.

## Edge cases

- A proposal targets an artifact whose owner workspace has since been archived or removed.
- Two proposals target the same artifact concurrently; the second reviewed MUST re-validate against
  the artifact's latest published version, not the state at proposal creation.
- A promotion request is submitted for an artifact that still has an open, unresolved proposal.
- A user loses workspace membership between proposing and the proposal's review.
- The service account's PR is closed without merging (rejection path): the proposal MUST return to
  a `rejected` status with the reviewer's reason, and MUST NOT silently retry.
- A discoverable personal artifact's owner leaves the company: discoverability MUST NOT silently
  become install access for anyone.

## Non-goals (this version)

- Automatic ownership transfer or reputation-based rights.
- Cross-repository proposals (the target repository is always the artifact's existing declared
  repository).
- Automatic demotion of scope based on inactivity.
- Company-wide full-text discovery across all personal workspaces regardless of the `discoverable`
  flag.

## Success criteria

- **SC-001**: A user with no Git knowledge submits a Skill improvement from an MCP-connected client
  and it appears as a reviewable proposal within the same interaction.
- **SC-002**: 100% of proposals that fail the archive validator are rejected before reaching a human
  reviewer.
- **SC-003**: Promoting an artifact from `team` to `group` scope requires zero content re-upload and
  preserves 100% of its version and installation history.
- **SC-004**: No proposal ever produces an `artifact_version` without a verified merged commit SHA.
- **SC-005**: A discoverable personal-workspace artifact is findable by name from another workspace
  in under the same search latency budget as `017-real-capability-catalog` (`SC-007` parity), while
  remaining non-installable without explicit access.
