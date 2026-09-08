# Plan d'implémentation — Cycle de vie autonome des sources

**Branche** : `feat-source-lifecycle` | **Date** : 2026-09-08 | **Spec** : [spec.md](spec.md)

## Résumé

Étendre le monolithe modulaire existant avec un agrégat transactionnel `SourceFlow`, une
planification à intervalle durable et une projection de santé. Les routes FastAPI, les futurs outils
MCP et le worker réutilisent le même service applicatif et le même dépôt PostgreSQL.

## Contexte technique

- **Langage** : Python 3.14.
- **Dépendances** : FastAPI, Pydantic v2, SQLAlchemy 2, asyncpg, Alembic.
- **Stockage** : Neon PostgreSQL ; références secrètes opaques vers Infisical.
- **Tests** : pytest, Ruff, mypy, tests de contrat et d'intégration.
- **Déploiement** : API et ordonnanceur séparés, même code et mêmes contrats.
- **Performance** : lecture de santé p95 < 300 ms ; transaction courte sans I/O externe.

## Contrôle constitutionnel

- Spécification et traçabilité avant code : conforme.
- Monolithe modulaire et service partagé API/MCP/worker : conforme.
- Autorisation serveur et refus par défaut : conforme.
- Aucun secret en base ; référence opaque seulement : conforme.
- Planification et transitions déterministes : conforme.
- Migration additive, outbox, idempotence et rollback par désactivation : conforme.

## Architecture

```text
FastAPI / futur MCP
        │
SourceLifecycleService
        │
transaction PostgreSQL ── source + asset + contract + pipeline + schedule + outbox
        │
SchedulerWorker ── réclame les échéances ── crée un run durable
        │
WebCaptureWorker existant ── capture ── snapshot + qualité + contenu
```

## Structure concernée

```text
apps/backend/src/kya_platform/
├── application/source_lifecycle/
├── domain/source_lifecycle/
├── infrastructure/database/source_lifecycle.py
├── infrastructure/database/models/data.py
├── api/routes/source_lifecycle.py
└── workers/source_scheduler.py
```

## Retour arrière

Désactiver le runtime d'ordonnancement et retirer les routes. La table additive de planification et
les événements restent disponibles pour audit. Aucun snapshot existant n'est modifié.
