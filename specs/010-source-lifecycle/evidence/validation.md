# Validation — Cycle de vie autonome des sources v0.1

Date : 2026-09-08

## Qualité logicielle

- Ruff et mypy validés ; 136 fichiers Python typés sans erreur.
- 506 tests backend réussis ; couverture globale de 90,04 %.
- CI monorepo, modèle OpenFGA, preview Neon, détection de secrets, builds, scans Trivy et
  SBOM validés sur la PR 42.
- Migration Alembic additive générée hors ligne puis appliquée transactionnellement.

## Preuves d'environnement de développement

- Branche Neon : `br-calm-mountain-axba3587`.
- Base canonique : `kya_platform`.
- Révision Alembic observée après migration : `20260908_0015 (head)`.
- Commit déployé : `c27ec819fcd21b41418e119c0a749d3c4d43f3a3`.
- `kya-platform-backend` : `running:healthy` sur le commit attendu.
- `kya-platform-source-scheduler` : déploiement terminé et processus actif sur le même commit ;
  aucun endpoint public ni healthcheck HTTP n'est exposé par conception.
- `GET /api/v1/health/ready` : `status=ok`.
- Les routes de collection et de santé des flux sont présentes dans OpenAPI.
- Un appel MCP sans authentification reste refusé avec HTTP 401.

## Limites de cette preuve

La création d'un flux réel par un utilisateur sera le test d'acceptation du premier connecteur de
la phase suivante. La présente preuve valide le socle, son déploiement et ses frontières de
sécurité ; elle ne prétend pas valider une nouvelle source métier.
