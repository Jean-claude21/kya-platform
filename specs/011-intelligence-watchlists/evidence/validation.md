# Preuves de validation — KYA Intelligence v0.1

**Date** : 2026-09-08  
**Commit déployé sur `dev`** : `3cfd978a931c376567c2369b6bfa9d9a01d082db`

## Qualité

- Ruff : réussi.
- mypy : 144 fichiers source, aucune erreur.
- pytest : suite complète réussie, couverture globale 90,00 %.
- CI PR #44 : qualité, backend, autorisation, dépendances/secrets, preview, conteneurs et SBOM
  réussis.
- Alembic : un seul head `20260908_0016`.

## Neon

- Migration appliquée sur la branche de développement validée.
- Révision courante confirmée : `20260908_0016 (head)`.
- Schéma additif `intelligence` présent.
- Cinq définitions d'outils Intelligence synchronisées dans `mcp_control.tool_definition`.
- Zéro veille créée par procédure technique : la première création reste attribuée à l'identité de
  l'utilisateur MCP.

## Déploiement

- Application Coolify : branche `dev`.
- Commit épinglé : `3cfd978a931c376567c2369b6bfa9d9a01d082db`.
- État : `running:healthy`.
- `GET /api/v1/health/ready` : `status=ok`.
- Quatre chemins HTTP Intelligence visibles dans OpenAPI, couvrant cinq opérations.
- MCP refuse toujours une requête non authentifiée avec HTTP 401.

## Données pilotes

- Recherche lexicale déterministe `solaire` : 16 fragments correspondants dans le corpus gouverné.
- Les sources et snapshots existants n'ont pas été modifiés.
- Le pilote utilisateur final consiste à créer `veille-solaire`, l'évaluer puis lister ses signaux
  depuis le connecteur KYA-Platform authentifié.
