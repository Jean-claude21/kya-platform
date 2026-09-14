# Artifact installation integrity

KYA-Platform installation plans are client-consented and fail closed. The platform never writes
into Claude Code, Codex or another client environment. It returns an immutable package locator and
a machine-readable integrity locator; the client downloads, verifies, stages and activates the
package before it confirms the receipt.

## Verification contract

Installation plan schema version 2 points the signature and digest steps to a release integrity
document. That document provides:

- the SHA-256 digest of the ZIP transport bytes;
- the complete ordered file inventory, with size and SHA-256 for every file;
- the exact canonical payload as Base64-encoded UTF-8 bytes;
- the canonicalization identifier `kya-content-inventory-v1`;
- the Ed25519 signature, signed payload, key identifier and public verification key.

For `kya-content-inventory-v1`, the client first checks every extracted file against the inventory.
It then excludes `artifact.manifest.json`, orders the remaining records by POSIX path, serializes
only `path`, `sha256` and `size` as compact JSON with sorted keys, and hashes the UTF-8 bytes with
SHA-256. The supplied canonical payload removes JSON implementation ambiguity and must produce the
same digest.

The client verifies the Ed25519 signature over the supplied domain-separated signed payload. Only
after all checks pass may it send that content digest as `installed_digest` to
`confirm_installation`. A mismatch leaves the plan unconfirmed and must never be bypassed.

## Current Design System release

The immutable KYA Design System 0.1.1 package is available at its package locator. Its corresponding
integrity document is exposed at:

```text
https://api.kya-platform.vttlife.com/api/v1/releases/kya-design-system/0.1.1/integrity
```

The Registry MCP includes this URL in every new installation plan, so an AI client does not need to
infer an endpoint or reverse-engineer the digest algorithm.
