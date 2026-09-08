# Plan d'implémentation — Profils d'outils MCP gouvernés

**Branche** : `feat-mcp-tool-profiles`  
**Date** : 2026-09-08  
**Spec** : [spec.md](spec.md)

## Résumé

Ajouter un registre persistant des outils et des profils, calculer une liste effective bornée par
identité/unité/client, puis l'appliquer uniformément à `tools/list` et `tools/call` sur la passerelle
MCP existante.

## Contexte technique

- Python 3.14, FastAPI, SQLAlchemy 2, Alembic, SDK MCP Python ;
- Neon PostgreSQL pour le plan de contrôle ; OpenFGA pour les grants ;
- pytest, Ruff, mypy et tests du modèle OpenFGA ;
- Streamable HTTP stateless MCP `2026-07-28` ;
- objectif : 24 outils maximum, p95 inférieur à 200 ms à chaud.

## Contrôle constitutionnel

- Spec Kit et preuves reliées : conforme.
- Une seule passerelle et services partagés : conforme.
- Refus par défaut, active unit, aucune clé en base : conforme.
- IA ne décide ni grants ni transitions : conforme.
- Migration additive, feature flag, tests et rollback : conforme.

## Étapes

1. Ajouter migration, modèles et seed déterministe de `ALL_TOOLS`.
2. Implémenter le résolveur pur et le dépôt PostgreSQL.
3. Ajouter shadow mode et métriques de divergence.
4. Étendre OpenFGA avec profils et droits d'outil, puis activer l'enforcement.
5. Ajouter API de lecture/mutation avec révision optimiste et audit.
6. Brancher le résolveur sur `tools/list` et refaire la vérification à `tools/call`.
7. Valider sur Neon dev, déployer et tester avec le compte pilote.

## Rollback

Le feature flag repasse au filtre historique. Les tables additives restent présentes afin de ne
perdre ni configuration ni audit. Staging et production ne sont pas modifiés sans promotion.
