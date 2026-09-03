# Implementation Plan: Fondation de KYA Platform

**Branch**: `feat-platform-foundation` | **Date**: 2026-09-03 |
**Spec**: [spec.md](./spec.md)

## Summary

Construire un plan de contrôle interne qui gouverne les espaces, identités, autorisations,
artefacts, publications, installations, secrets référencés et déploiements de KYA. La première
livraison est un monolithe modulaire polyglotte : interface TanStack en TypeScript et noyau métier
FastAPI en Python, exposé par API, MCP et workers. Les données du Hub résident dans Neon,
l'autorisation dans OpenFGA et les secrets dans Infisical.
GitHub porte les sources et validations ; Dokploy et Coolify implémentent un même contrat.

## Technical Context

**Language/Version**: Python 3.13 pour le backend ; TypeScript strict et Node.js 24 LTS pour le Web
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, MCP Python SDK,
TanStack Start, Better Auth, OpenFGA, Zod, OpenTelemetry
**Storage**: Neon Postgres ; Infisical pour les valeurs secrètes ; stockage OpenFGA géré  
**Testing**: pytest, Vitest, Playwright, tests de contrats, tests de politiques et intégration conteneurisée
**Target Platform**: conteneurs Linux déployables par Dokploy ou Coolify  
**Project Type**: monorepo Web TypeScript + backend Python modulaire
**Performance Goals**: lecture catalogue p95 < 500 ms ; décision d'autorisation p95 < 100 ms ;
recherche p95 < 1 s à la charge pilote  
**Constraints**: refus par défaut, aucune valeur secrète dans Neon ou les logs, faible bande
passante, français initial, audit des actions sensibles, rollback  
**Scale/Scope**: pilote Groupe, plusieurs pays et Directions, 10 000 identités adressables,
100 000 artefacts/versions et 1 million de relations sans changement de modèle

## Constitution Check

| Gate                                      | Pre-design | Post-design | Evidence                                   |
| ----------------------------------------- | ---------: | ----------: | ------------------------------------------ |
| Spec Kit et traçabilité                   |       PASS |        PASS | spec, research, plan et futurs tasks       |
| Modules et contrats explicites            |       PASS |        PASS | structure workspace et contracts           |
| Source autoritaire déclarée               |       PASS |        PASS | Neon Hub, Frappe métier, Infisical secret  |
| Autorisation serveur et moindre privilège |       PASS |        PASS | OpenFGA + matrice négative                 |
| Aucun secret dans le catalogue            |       PASS |        PASS | SecretReference uniquement                 |
| IA séparée de l'exécution                 |       PASS |        PASS | Skill ≠ outil MCP ; handlers déterministes |
| Tests, audit et rollback                  |       PASS |        PASS | pipeline, événements et quickstart         |
| Preview isolée                            |       PASS |        PASS | branche Neon et secrets non productifs     |

Aucune exception constitutionnelle n'est demandée.

## Architecture

```text
Utilisateurs et agents IA
        │
        ├── apps/web (TanStack Start + frontière d'identité)
        └── apps/backend (FastAPI)
                    ├── API métier versionnée
                    ├── Registry MCP protégé
                    └── workers et routines planifiées
                               │
                 modules de domaine Python
                               │
      ┌────────────────────────┼────────────────────────┐
 OpenFGA                  Neon PostgreSQL        GitHub / providers
      │                                               │
 Infisical                                     Dokploy ou Coolify
```

Les adapters dépendent des ports de domaine ; le domaine ne dépend d'aucun fournisseur. Les
workers exécutent synchronisation GitHub, détection quotidienne des mises à jour, expirations,
notifications et reprise des opérations idempotentes.

## Project Structure

```text
apps/
├── web/                     # Interface TanStack et frontière Better Auth
└── backend/                 # FastAPI : API, MCP, domaine, adapters et workers
    ├── src/kya_platform/
    │   ├── api/             # routes HTTP versionnées et dépendances
    │   ├── mcp/             # outils MCP et Protected Resource Metadata
    │   ├── workers/         # routines planifiées et asynchrones
    │   ├── domain/          # entités et invariants purs
    │   ├── application/     # cas d'usage, transactions et ports
    │   └── infrastructure/  # Neon, OpenFGA, Infisical et fournisseurs
    └── tests/
packages/
├── contracts/               # contrats TypeScript générés depuis OpenAPI/JSON Schema
├── config/                  # validation de configuration Web sans secret serveur
├── design-system/           # composants et tokens KYA
└── test-kit/                # builders et configuration de tests Web
catalog/templates/
├── skill/
├── mcp-server/
├── application/
└── connector/
infra/
├── containers/
├── github/
├── dokploy/
├── coolify/
├── neon/
└── observability/
docs/adr/
tests/
├── contract/
├── integration/
├── policy/
├── e2e/
└── security/
```

**Structure Decision**: FastAPI est l'unique backend métier. TanStack ne duplique ni règles
d'autorisation ni accès direct à Neon. Un Spec Kit à la racine gouverne la plateforme. Les futurs
artefacts autonomes pourront recevoir leur propre projet Spec Kit lors de leur extraction, sans
dupliquer les modèles partagés prématurément.

## Delivery Sequence

1. **Socle reproductible** : workspace, règles d'import, CI, images, variables validées.
2. **Organisation et IAM** : personnes, unités, affectations, espaces, rôles, relations et matrice.
3. **Catalogue** : artefacts, versions, autorités, recherche filtrée et Frappe enregistré.
4. **Publication** : manifeste, provenance, contrôles, approbations, signature et audit.
5. **Distribution** : découverte, installation, vérification quotidienne, mise à jour et rollback.
6. **MCP** : OAuth, Registry MCP en lecture, scopes par outil, puis demandes contrôlées d'écriture.
7. **Déploiement** : même scénario contre Dokploy et Coolify, choix primaire documenté.
8. **Pilotes factuels** : un Skill, un MCP, une application et un connecteur complets.
9. **Ouverture** : templates, leçons, délégation aux Directions et tableau de gouvernance.

Chaque séquence livre une tranche démontrable. Les séquences 2 et 3 peuvent progresser en parallèle
après stabilisation des identifiants et contrats ; 4 à 7 commencent avec des mocks de ports, puis
sont validées contre les vrais fournisseurs.

## Branch, Tag and Promotion Policy

```text
feat-xxx → PR dev → tag optionnel vX.Y.Z-dev.N → test
dev → PR main → tag obligatoire vX.Y.Z → production
```

- Aucun commit direct sur `main` ou `dev` après activation des règles GitHub.
- Chaque commit de `main` correspond exactement à un tag SemVer annoté.
- Un tag publié n'est jamais déplacé ni réutilisé.
- Correctif de production : `feat-hotfix-xxx` depuis `main`, puis report immédiat dans `dev`.
- Une image est construite une fois, attestée et promue par digest.

## Complexity Tracking

| Choix                         | Justification                                   | Condition de simplification                                                     |
| ----------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------- |
| OpenFGA                       | relations et héritages multi-périmètres         | retirer si le benchmark montre qu'un moteur embarqué couvre toute la matrice    |
| Deux providers de déploiement | portabilité demandée et comparaison factuelle   | conserver un seul adapter actif si le second n'apporte pas de reprise mesurable |
| Infisical distinct            | valeurs secrètes hors Hub et identités machines | aucun stockage maison autorisé ; seul le fournisseur peut changer               |
