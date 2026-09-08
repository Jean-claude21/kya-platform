# Validation locale

Date : 2026-09-08

- `uv run ruff check apps/backend` : succès
- `uv run ruff format --check apps/backend` : succès
- `uv run mypy` : succès, 119 fichiers
- `uv run pytest` : 437 tests réussis
- couverture backend : 90,19 %, seuil de 90 % atteint
- diagramme Mermaid validé et exporté avec Mermaid CLI 11.17.0

La validation distante et le contrôle du MCP déployé seront ajoutés après fusion dans `dev`.

## Validation distante

PR #36 : contrôles GitHub réussis — politique de branche, autorisations, qualité frontend,
qualité backend, preview Neon, validation du déploiement, dépendances/secrets, images et SBOM.
