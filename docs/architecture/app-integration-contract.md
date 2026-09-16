# KYA application integration contract

Every first-party or partner application integrates with KYA-Platform through the same three
boundaries:

1. **Identity** — the application obtains a Neon Auth access token for the KYA audience. It never
   creates a second user directory or stores a KYA password.
2. **Organizational context** — the user explicitly selects an active organizational unit and,
   when needed, a workspace. The application forwards these values on every Business API call.
3. **Effective authorization** — FastAPI validates the token and OpenFGA decides access in the
   active context. The interface may hide unavailable actions, but it is never the trust boundary.

The shared `@kya/platform-sdk` package implements the request boundary. It injects the Bearer token,
`X-KYA-Unit-ID`, optional `X-KYA-Workspace-ID`, and idempotency keys. It preserves structured API
errors so applications can distinguish authentication, permission, conflict, and availability
failures.

Applications own their métier screens and local workflow state. KYA Core remains authoritative for
organization, identities, clients, projects, permissions, catalogue metadata, audit, and shared
capabilities. An application references those records by identifier instead of copying them into a
new source of truth.

The current package is private to the monorepo while its API stabilizes. Publishing it to an
internal package registry is a separate governed release step; external repositories must not copy
an unpublished implementation by hand.
