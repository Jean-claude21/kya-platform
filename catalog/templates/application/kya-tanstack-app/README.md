# KYA governed application template

This is the standalone starting point for a KYA business application. It owns its product code,
tests and deployment while KYA-Platform remains the authority for identity, active context,
permissions, discovery and audit.

## Bootstrap

1. Replace every `replace-me` value in `artifact.manifest.json`.
2. Commit a generated `pnpm-lock.yaml`; CI deliberately requires a frozen lockfile.
3. Configure `VITE_KYA_API_URL` as a non-secret runtime value.
4. Create an Infisical machine identity for the deployed service. Store only the project,
   environment and secret-path references in deployment configuration; never commit secret values.
5. Register the published manifest in KYA-Platform. Users will only see the app when both its
   lifecycle and their effective `view`/`use` permissions allow it.

## Runtime boundary

`src/product-boundary.ts` is the only place that constructs `KyaPlatformClient`. The shell must
inject the access token and active context. Product screens consume typed SDK methods and do not
decode tokens or reconstruct organizational permissions.

## Delivery contract

- `GET /health` is served by the container without exposing dependencies or secrets.
- GitHub Actions runs one cancellable quality job and uses the pnpm cache.
- Deployment receives secrets from Infisical at runtime.
- The immutable image should be promoted between environments instead of rebuilt.
- Application events use KYA's versioned event envelope; outbound webhooks are sent by the
  platform outbox and signed with a referenced secret.

The template does not contain a deployment credential, database password, API token or personal
configuration.
