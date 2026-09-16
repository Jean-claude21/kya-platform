# Required credentials and machine identities

This page inventories expected access without recording secret values. Values are created in
Infisical and injected at runtime with least privilege.

## Current state

Local contracts and tests require no external key. Tests use local instances or controlled adapters.

## Just-in-time access

| Stage             | Required access                                | Purpose                               | Required separation         |
| ----------------- | ---------------------------------------------- | ------------------------------------- | --------------------------- |
| Neon persistence  | pooled runtime URL and direct migration URL    | API and Alembic                       | preview, test, production   |
| Identity          | Neon Auth URL, issuer, audience and JWKS       | sessions and tokens                   | per branch/environment      |
| Files             | Neon Object Storage S3 identity                | private objects and publications      | per branch/environment      |
| Authorization     | OpenFGA store/model and machine identity       | server decisions                      | per environment             |
| Secrets           | Infisical machine identity                     | resolve authorized references         | per workload/environment    |
| Synchronization   | GitHub App ID, installation ID and private key | repositories, PRs, tags and manifests | least privilege             |
| Deployment        | Dokploy and/or Coolify token                   | preview, promotion and rollback       | per provider/environment    |
| Frappe            | Frappe integration identity                    | authorized capabilities and data      | per site/scope              |
| Optional AI model | Z.AI key or compatible subscription            | GLM-5.3 through an adapter            | personal, pilot, production |

## Neon Object Storage mapping

The initial implementation maps five generic KYA runtime parameters to the same Neon Storage
branch:

| KYA parameter                          | Expected Neon Storage value                 |
| -------------------------------------- | ------------------------------------------- |
| `KYA_OBJECT_STORAGE_ENDPOINT_URL`      | branch S3 HTTPS endpoint                    |
| `KYA_OBJECT_STORAGE_REGION`            | region supplied for the endpoint            |
| `KYA_OBJECT_STORAGE_BUCKET`            | bucket declared in `neon.ts` (`kya-data`)   |
| `KYA_OBJECT_STORAGE_ACCESS_KEY_ID`     | branch S3 access key                        |
| `KYA_OBJECT_STORAGE_SECRET_ACCESS_KEY` | associated secret key, read only at runtime |

`KYA_NEON_API_KEY` and `KYA_NEON_PROJECT_ID` control the Neon control plane; they never replace S3
credentials. Development, preview/staging and production use distinct values so file isolation
follows Neon branches.

Before the first real connection, CVSI receives the exact requested permissions, creation
procedure, owner, lifetime, rotation plan and revocation test.
