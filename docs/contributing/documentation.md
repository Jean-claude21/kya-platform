# Documentation workflow

English is the canonical language for maintained KYA Platform documentation, source comments,
contracts and artifact templates. Historical specifications may remain in their original language
until they are revised; new or materially revised specifications use English.

## Definition of done

A feature is not complete until the relevant documentation agrees with its implementation and
tests. Each `feat-*` Pull Request must update the applicable items:

1. Spec Kit documents for intent, scope and acceptance criteria.
2. An ADR for a durable architectural decision or trade-off.
3. Mermaid or C4 diagrams when three or more components interact.
4. User or operator guidance for a new observable workflow.
5. FastAPI metadata and models for API contract changes.
6. MCP tool descriptions and schemas for MCP changes.
7. Storybook stories for Design System component changes.

## Local commands

```bash
pnpm docs:serve
pnpm docs:build
```

The strict build fails on invalid navigation, unresolved internal links and other documentation
warnings. CI runs the same build before a feature can be merged.
