# KYA Zoom MCP

First governed business capability implemented inside the KYA-Platform monorepo.

## Initial tools

- `prepare_zoom_meeting`: validates time and policy, then creates a 15-minute plan.
- `create_zoom_meeting`: confirms a plan and creates the meeting idempotently.
- `list_zoom_meetings`: lists upcoming meetings for the resolved KYA connection.
- `get_zoom_meeting`: returns one safe meeting projection.

The provider adapter never returns Zoom's privileged `start_url`. A caller only
receives the participant `join_url` and non-privileged meeting metadata.

## Runtime boundaries

The MCP does not own users, organizational structure, permissions, or raw
secrets. KYA-Platform provides verified identity and context, policy decisions,
connection resolution, audit, and secret references. Infisical resolves the
three Zoom Server-to-Server OAuth values at deployment time.

The in-memory plan and operation stores are for contract tests only. A deployed
instance must use the shared KYA operation store so retries remain idempotent
across replicas.

## Local quality checks

```bash
uv run --package kya-zoom-mcp ruff check capabilities/mcp/zoom
uv run --package kya-zoom-mcp ruff format --check capabilities/mcp/zoom
uv run --package kya-zoom-mcp mypy capabilities/mcp/zoom/src
uv run --package kya-zoom-mcp pytest capabilities/mcp/zoom/tests
```
