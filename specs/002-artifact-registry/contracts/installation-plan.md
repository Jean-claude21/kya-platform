# Contract — governed installation plan

## Trust boundary

`get_artifact` keeps a stable, metadata-only response contract. A caller never has to discover,
invent, or ask the user for a release UUID.

The MCP `request_install` tool accepts the public artifact identifier and an optional version. The
server resolves the newest published release compatible with the requested client profile. It also
defaults the target to the caller's active unit, the scope to `personal`, the profile to
`claude-code`, and the client baseline to `2026-09`. Consequently, an agent can fulfill a natural
request such as “install KYA Design System” after catalog discovery without exposing technical
installation parameters to the user.

For the first immutable KYA Skill releases, a bounded compatibility bridge treats an explicit
`codex` requirement as valid for the `claude-code` filesystem profile. Those packages already use
the shared Agent Skills directory structure. The bridge applies only to Skills; new releases must
declare every supported profile explicitly in their manifest.

`request_install` does not write files. After OAuth and OpenFGA authorization, the Registry loads a
published release from Neon, verifies its digest and Ed25519 signature, then checks the target
profile and client compatibility. It returns an immutable plan. The client remains responsible for
showing the target, obtaining consent, and performing local writes.

## Minimal MCP input

- `artifact_id`;
- optional `version`, `profile`, `scope`, `target`, and `client_version` overrides.

Defaults are safe for a personal Claude installation in the caller's active KYA unit. Advanced
clients may explicitly select `codex`, `claude-code`, or `portable-zip`, and `personal` or `project`.

### Cached-schema compatibility

Some remote AI clients keep a tool schema for the lifetime of an existing conversation. During the
0.2 transition, `request_install` therefore also accepts the former resolved `release_id`,
idempotency, and confirmation fields. For those already-open sessions, the metadata-only artifact
summary carries a temporary installation hint containing the authorized release UUID and safe
defaults. The structured `get_artifact` schema remains unchanged, avoiding the strict-output
validation failure that prompted the compatibility bridge. Fresh clients should send only
`artifact_id`; server-side release resolution remains the canonical path.

## Internal resolved input

After release resolution, the backend receives the exact `release_id`, target, profile, scope,
client version, a strong idempotency key, and structured confirmation. These technical values stay
inside KYA-Platform and are never requested from the end user.

## Output

The plan contains the release identity, digest, content-addressed locator, compatibility constraint,
symbolic destination, and exactly seven typed actions:

1. fetch the package into a temporary area;
2. verify the release signature;
3. verify the content digest;
4. verify client compatibility;
5. stage files without activation;
6. activate atomically in the consented destination;
7. write a local receipt for audit and rollback.

The plan contains no shell command, secret value, or server-imposed absolute path. Identical
release, target, profile, scope, and client version values always produce the same plan UUID.

## Symbolic destinations

| Profile      | Personal                                          | Project                 |
| ------------ | ------------------------------------------------- | ----------------------- |
| Codex        | `${CODEX_PERSONAL_SKILLS_DIR}/{slug}`             | `.agents/skills/{slug}` |
| Claude Code  | `~/.claude/skills/{slug}`                         | `.claude/skills/{slug}` |
| Portable ZIP | `${USER_SELECTED_DIRECTORY}/{slug}-{version}.zip` | same                    |

Codex and Claude Code filesystem profiles currently accept Skills only. Other artifact types use
the portable ZIP profile until a dedicated, tested, governed installer exists.
