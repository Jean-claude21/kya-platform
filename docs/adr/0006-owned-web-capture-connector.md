# ADR 0006 — First connector: KYA-owned Web capture

## Decision

The first real connector captures KYA's institutional website. A separate worker processes an
outbox event and writes a canonical JSON package to S3-compatible storage. Neon Object Storage is
the initial provider; the domain does not depend on Neon.

## Rationale

- The source is useful, public and controlled by KYA.
- It validates the real MCP → Data → outbox → capture → storage → snapshot path.
- It creates a reusable foundation for editorial control, SEO, product knowledge and change
  detection.
- It carries less risk than a first pilot on a third-party platform.
- Deterministic software collects; AI performs subsequent analysis.

## Consequences

- Data sources contain public JSON configuration; secrets remain referenced.
- Each run pins its configuration, asset and contract in the event.
- Capture uses HTTPS, stays on the same origin, respects bounded limits and `robots.txt`, and does
  not require a browser.
- Non-HTML content and secondary failures become quality warnings.
- Activation requires Neon Storage S3 credentials in Infisical.

A future public-procurement connector may reuse the Data protocol and storage port, while retaining
its own source logic, compliance rules and business contract.
