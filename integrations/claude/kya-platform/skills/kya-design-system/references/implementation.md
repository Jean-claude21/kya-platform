# Implementation reference

Use the shared `@kya/design-system` package and its CSS tokens. Do not redefine brand colors in a
feature component. Use authored SVG icons from the package rather than emoji or an unrelated icon
library. When the Group logo is required, copy
`assets/brand/kya-energy-group-logo.png` from this Skill without modifying its pixels or aspect
ratio.

The application shell has three product zones:

1. employee use: Home, Catalogue, Apps, MCP, Skills, Workspaces;
2. governed creation: Studio;
3. control plane: Organization, KYA Core, Systems, Secret references, Publication, Audit.

Authentication may use the approved photographic assets under `/images/auth`. Working screens
remain focused on operational content. All API-derived content needs loading, empty, error, and
partial-access handling.
