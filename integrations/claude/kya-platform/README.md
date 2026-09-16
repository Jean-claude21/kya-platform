# KYA-Platform for Claude

This plugin is the Claude delivery mode for KYA-Platform. It installs two things as one governed
unit:

- the official `kya-platform:kya-design-system` skill;
- the remote KYA-Platform MCP connection, authenticated through OAuth.

Claude Code 2.1.196 or newer is required for the pinned OAuth scope configuration. Current Claude
cloud sessions managed from claude.ai receive the plugin through account or organization sync.

The plugin does not contain a password, OAuth token, client secret, or private key. Claude opens the
KYA-Platform authorization flow on first MCP use and KYA-Platform computes the effective tools from
the authenticated identity and active organizational context.

## Install from the KYA marketplace

In Claude Code:

```text
/plugin marketplace add Jean-claude21/kya-platform
/plugin install kya-platform@kya-platform
```

Before the plugin reaches the repository's default branch, maintainers test the `dev` channel with
`/plugin marketplace add Jean-claude21/kya-platform@dev`.

Restart Claude Code or run `/reload-plugins` when requested. The first use of a KYA-Platform tool
opens the OAuth consent flow. The skill is then available as
`/kya-platform:kya-design-system` without a separate KYA catalogue installation.

For Claude Team or Enterprise, an owner can add this repository as a private plugin marketplace in
the Claude administration settings. Enabled plugins are synchronized into Claude cloud sessions.

## Update

The plugin version is the update boundary. After a new reviewed skill or MCP configuration is
published, bump the version in both `plugin.json` and the marketplace entry. Claude Code users can
refresh the marketplace and update the plugin:

```text
/plugin marketplace update kya-platform
/plugin update kya-platform@kya-platform
```

Organization-managed Claude sessions receive the version selected by the owner at the next plugin
refresh/session. KYA-Platform remains the source of authorization; updating the plugin does not
grant additional server-side rights.

## Trust model

- Plugin installation supplies code-free instructions, brand assets, and an MCP endpoint.
- OAuth supplies identity and revocable consent.
- KYA-Platform policies decide which tools and resources are visible.
- Published plugin and skill versions are immutable; every change requires a new version.
- The packaged skill is byte-for-byte identical to the published KYA catalogue release checked by
  `infra/claude/package_plugin.py`.
