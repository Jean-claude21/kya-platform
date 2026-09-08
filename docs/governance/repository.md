# KYA Platform repository governance

Last reviewed: 2026-09-05.

## Required flow

- `feat-xxx` starts from `dev` and returns to `dev` through a Pull Request.
- `dev` is the integration branch; optional `vX.Y.Z-dev.N` tags mark deployable milestones.
- Only `dev` may open a Pull Request to `main`.
- Every commit accepted on `main` receives an annotated SemVer tag.
- Feature branches never push directly to `main`.

Workflows already check branch direction, linting, types, tests, the OpenFGA model, secrets,
container images and SBOMs.

## Owners and approvals

The private repository currently has one direct administrator, `Jean-claude21`. GitHub therefore
cannot yet demonstrate separation of duties with two independent accounts. Sensitive changes still
require separate functional and technical decisions in KYA Platform, even when GitHub cannot
materialize two approvers.

## GitHub protection currently unavailable

The GitHub API returns `403` for `main` and `dev` protection because the private repository plan
must be upgraded. The repository must not be made public to bypass this restriction.

Task T080 remains open. Once the feature is available and a second owner is appointed:

- deny direct pushes and deletion of `main`;
- require a `dev → main` Pull Request, independent approval and all checks;
- deny administrator bypass outside an audited emergency process;
- require `feat-xxx → dev` Pull Requests and quality/security checks;
- retain a release-compatible history and never squash an already published tag.
