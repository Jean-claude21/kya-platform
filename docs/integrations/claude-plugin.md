# Claude plugin

KYA-Platform is delivered to Claude as a plugin, not as a prompt asking Claude to copy files. The
plugin is a client delivery mode alongside Codex, Claude Code, and portable ZIP packages.

The same plugin model also exists in Claude itself: plugins enabled for a claude.ai account are
synchronized into Claude cloud sessions. Claude Code 2.1.196 or newer is required when installing
the marketplace directly from a terminal because this integration pins its approved OAuth scopes.

## What the plugin contains

The first release contains the KYA Design System skill and the remote KYA-Platform MCP declaration.
The skill is available immediately after plugin activation. The MCP authenticates the person through
OAuth and exposes only the tools allowed by KYA-Platform policy.

This separation is intentional:

| Responsibility | Owner |
| --- | --- |
| Install the skill and MCP declaration | Claude plugin manager |
| Authenticate the person | KYA-Platform OAuth |
| Decide visible tools and data | KYA-Platform policy engine |
| Publish immutable skill content | KYA-Platform catalogue |
| Deliver a reviewed plugin version | GitHub marketplace and CI |

The plugin never embeds credentials. Its MCP request is capped to catalogue installation and
read-only data scopes; the server may grant fewer scopes based on the user and active unit.

## User journey

1. The user or Claude organization owner installs `KYA-Platform` from the KYA marketplace.
2. Claude loads the bundled skill and MCP declaration.
3. On the first KYA tool call, Claude opens the KYA-Platform OAuth consent flow.
4. KYA-Platform resolves the authenticated identity, active unit, policies, and effective tools.
5. Claude can apply the Design System and call the authorized KYA tools.

There is no second `request_install` call for the bundled Design System skill. That catalogue flow is
still used for client profiles that install standalone KYA artifacts.

## Release and update model

The source of truth remains the immutable catalogue release. CI verifies that every file bundled in
the plugin is byte-for-byte identical to `catalog/releases/kya-design-system/<version>.zip` and that
the plugin, marketplace, and skill versions match.

Every change requires:

1. publish the reviewed skill release;
2. copy that exact release into the plugin;
3. bump the plugin and marketplace versions;
4. validate and build the deterministic plugin archive;
5. merge through CI and release from GitHub.

Claude Code retrieves updates from the marketplace. Claude Team and Enterprise owners can select or
require the published plugin version for synchronized Claude cloud sessions. OAuth grants and server
policies remain revocable independently from plugin versions.

## Validation

```bash
python infra/claude/package_plugin.py --check
python infra/claude/package_plugin.py
claude plugin validate integrations/claude/kya-platform --strict
claude plugin validate . --strict
```

The Python validator is always run in CI. The Claude CLI validator is an additional release gate on a
maintainer workstation or release runner that has a compatible Claude Code CLI.
