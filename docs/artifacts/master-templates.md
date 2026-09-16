# Master artifact templates

KYA maintains one governed master template per artifact family. A template is copied into
`catalog/sources` to create a real artifact. It is never published directly. A validated,
versioned package is promoted to `catalog/releases`.

```text
master template → editable source → validation → approval → immutable release
catalog/templates  catalog/sources                 catalog/releases
```

## Master Skill template

Location: `catalog/templates/skill/kya-business-method`

```text
kya-business-method/
├── SKILL.md                   required instructions and routing
├── agents/
│   └── openai.yaml            discovery and user-facing metadata
├── references/
│   └── method.md              detailed method loaded only when needed
└── artifact.manifest.json     identity, ownership, version and integrity
```

Optional directories are added only when the Skill needs them:

- `assets/` for files copied into generated deliverables;
- `templates/` for reusable document or project templates;
- `schemas/` for machine-verifiable inputs and outputs;
- `scripts/` for deterministic operations;
- `tests/` for executable behavior;
- `examples/` for examples that materially clarify the method.

A code-bearing Skill must also declare `capability.manifest.json`, tests and `sbom.cdx.json`. The
capability manifest requests an execution envelope; it never grants authorization.

## Master MCP server template

Location: `catalog/templates/mcp-server/kya-capability-mcp`

```text
kya-capability-mcp/
├── artifact.manifest.json     ownership, version, scopes and risk
├── capability.manifest.json   runtime and requested execution envelope
├── sbom.cdx.json              software bill of materials
├── pyproject.toml
├── src/kya_capability_mcp/
│   ├── contracts.py           typed inputs and outputs
│   ├── service.py             business-facing port and deterministic logic
│   └── server.py              thin MCP delivery layer
└── tests/
    └── test_service.py
```

The normal KYA choice is to add a capability to the existing governed MCP gateway. A separate MCP
server is justified only by an independent trust boundary, owner, runtime, scaling need or release
lifecycle. In both cases, tools call application services or the Business API; they do not bypass
authorization, audit or data contracts.

## Visibility rule

The Platform catalog will expose the same structure, owners, current version, permissions,
dependencies and validation status through the Web interface and MCP. Authorized users can inspect
the template before creating an artifact and compare a source against its master template.
