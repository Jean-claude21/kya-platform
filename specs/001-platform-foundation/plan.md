# Implementation Plan: Fondation de KYA Platform

**Branch**: `feat-platform-foundation` | **Date**: 2026-09-03 |
**Spec**: [spec.md](./spec.md)

## Summary

Construire un plan de contrôle interne qui gouverne les espaces, identités, autorisations,
artefacts, publications, installations, secrets référencés et déploiements de KYA. La première
livraison est un monolithe modulaire TypeScript : interface TanStack, API et MCP partageant des
services de domaine, données du Hub dans Neon, autorisation OpenFGA et secrets dans Infisical.
GitHub porte les sources et validations ; Dokploy et Coolify implémentent un même contrat.

## Technical Context

**Language/Version**: TypeScript strict, Node.js 24 LTS  
**Primary Dependencies**: TanStack Start, Hono, MCP TypeScript SDK v2, Better Auth, OpenFGA,
Drizzle, Zod, OpenTelemetry  
**Storage**: Neon Postgres ; Infisical pour les valeurs secrètes ; stockage OpenFGA géré  
**Testing**: Vitest, Playwright, tests de contrats, tests de politiques et intégration conteneurisée  
**Target Platform**: conteneurs Linux déployables par Dokploy ou Coolify  
**Project Type**: monorepo Web/API/MCP/worker modulaire  
**Performance Goals**: lecture catalogue p95 < 500 ms ; décision d'autorisation p95 < 100 ms ;
recherche p95 < 1 s à la charge pilote  
**Constraints**: refus par défaut, aucune valeur secrète dans Neon ou les logs, faible bande
passante, français initial, audit des actions sensibles, rollback  
**Scale/Scope**: pilote Groupe, plusieurs pays et Directions, 10 000 identités adressables,
100 000 artefacts/versions et 1 million de relations sans changement de modèle

## Constitution Check

| Gate | Pre-design | Post-design | Evidence |
|---|---:|---:|---|
| Spec Kit et traçabilité | PASS | PASS | spec, research, plan et futurs tasks |
| Modules et contrats explicites | PASS | PASS | structure workspace et contracts |
| Source autoritaire déclarée | PASS | PASS | Neon Hub, Frappe métier, Infisical secret |
| Autorisation serveur et moindre privilège | PASS | PASS | OpenFGA + matrice négative |
| Aucun secret dans le catalogue | PASS | PASS | SecretReference uniquement |
| IA séparée de l'exécution | PASS | PASS | Skill ≠ outil MCP ; handlers déterministes |
| Tests, audit et rollback | PASS | PASS | pipeline, événements et quickstart |
| Preview isolée | PASS | PASS | branche Neon et secrets non productifs |

Aucune exception constitutionnelle n'est demandée.

## Architecture

```text
Utilisateurs et agents IA
        │
        ├── apps/web (TanStack Start)
        ├── apps/api (Business API + OAuth resource surfaces)
        └── apps/registry-mcp (outils MCP filtrés par identité)
                         │
                  packages/application
                         │
      ┌──────────────────┼──────────────────┐
 packages/iam      packages/catalog   packages/delivery
      │                   │                  │
 OpenFGA          Neon PostgreSQL      GitHub / providers
      │                                      │
 packages/secrets ── Infisical      Dokploy ou Coolify
```

Les adapters dépendent des ports de domaine ; le domaine ne dépend d'aucun fournisseur. Les
workers exécutent synchronisation GitHub, détection quotidienne des mises à jour, expirations,
notifications et reprise des opérations idempotentes.

## Project Structure

```text
apps/
├── web/                     # Interface et BFF TanStack
├── api/                     # API externe versionnée
├── registry-mcp/            # Serveur MCP distant
└── worker/                  # tâches planifiées et asynchrones
packages/
├── domain/                  # entités et invariants purs
├── application/             # cas d'usage et transactions
├── contracts/               # schémas publics et manifestes
├── db/                      # Drizzle, migrations, repositories
├── auth/                    # sessions et OIDC/OAuth
├── authorization/           # ports et adapter OpenFGA
├── secrets/                 # SecretReference et adapter Infisical
├── catalog/                 # artefacts, versions, capacités
├── organization/            # unités, espaces et affectations
├── publication/             # revue et cycle de vie
├── distribution/            # installation et mises à jour
├── deployment/              # contrat Dokploy/Coolify
├── audit/                   # événements append-only
├── frappe-adapter/          # système externe référencé
├── design-system/           # composants et tokens KYA
└── test-kit/                # builders, fixtures et matrices
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

**Structure Decision**: un Spec Kit à la racine gouverne la plateforme. Les futurs artefacts
autonomes pourront recevoir leur propre projet Spec Kit lors de leur extraction, sans dupliquer
les modèles partagés prématurément.

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

| Choix | Justification | Condition de simplification |
|---|---|---|
| OpenFGA | relations et héritages multi-périmètres | retirer si le benchmark montre qu'un moteur embarqué couvre toute la matrice |
| Deux providers de déploiement | portabilité demandée et comparaison factuelle | conserver un seul adapter actif si le second n'apporte pas de reprise mesurable |
| Infisical distinct | valeurs secrètes hors Hub et identités machines | aucun stockage maison autorisé ; seul le fournisseur peut changer |
