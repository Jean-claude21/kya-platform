# Implementation Plan: Registre des artefacts KYA

**Branch**: `feat-artifact-registry` | **Date**: 2026-09-06 | **Spec**: [spec.md](./spec.md)

## Summary

Étendre le monolithe modulaire existant avec un registre Neon persistant, un validateur de paquets
multi-fichiers, une API versionnée et le Registry MCP OAuth. La première tranche publie un Skill
réel sans exécuter son contenu et produit un plan d'installation portable.

## Technical Context

**Language/Version**: Python 3.14, TypeScript strict, Node.js 24 LTS  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, MCP Python SDK, OpenFGA  
**Storage**: Neon PostgreSQL ; GitHub pour sources ; port Blob/OCI pour paquets publiés  
**Testing**: pytest, tests de contrat, intégration PostgreSQL, politiques OpenFGA, sécurité archives  
**Target Platform**: conteneurs Linux, clients Codex et Claude Code  
**Performance Goals**: catalogue p95 < 500 ms ; recherche p95 < 1 s  
**Constraints**: refus par défaut, aucune exécution à l'ingestion, aucun secret, 100 MiB/2 000 fichiers  
**Scale/Scope**: 100 000 artefacts/versions, 10 000 identités adressables

## Constitution Check

| Gate                    | Pre-design | Post-design | Evidence                                    |
| ----------------------- | ---------: | ----------: | ------------------------------------------- |
| Spec Kit et traçabilité |       PASS |        PASS | spec, research, plan, tasks                 |
| Modules et contrats     |       PASS |        PASS | domaine, application, ports, adapters       |
| Source autoritaire      |       PASS |        PASS | Neon métadonnées, Git travail, blob contenu |
| Moindre privilège       |       PASS |        PASS | OAuth + OpenFGA + unité active              |
| Aucun secret            |       PASS |        PASS | références uniquement                       |
| IA ≠ exécution          |       PASS |        PASS | Registry sans exécution de paquet           |
| Tests et rollback       |       PASS |        PASS | matrice sécurité, versions immuables        |

Aucune exception constitutionnelle.

## Architecture

```text
Claude / Codex / Web
        │ OAuth + unité active
API FastAPI et Registry MCP
        │ mêmes cas d'usage
Catalog Service ─ Package Validator ─ Publication ─ Distribution
        │                 │                 │             │
      Neon          analyse statique      Outbox      profil cible
        │                                   │
     OpenFGA                         GitHub + Blob/OCI
```

## Delivery Sequence

1. Contrats v2 et invariants d'un paquet multi-fichiers.
2. Schéma Neon et repository transactionnel.
3. Création et lecture API avec autorisation.
4. Recherche filtrée et Registry MCP authentifié.
5. Validations, attestations et publication réelle.
6. Résolution d'installation Codex/Claude Code/zip.
7. Mise à jour, suspension, révocation et audit.
8. Interface de contribution et pilote métier.

## Project Structure

```text
apps/backend/src/kya_platform/
├── domain/catalog/
├── application/catalog/
├── infrastructure/database/catalog.py
├── infrastructure/database/models/catalog.py
├── api/routes/artifacts.py
└── mcp/registry/
catalog/templates/
specs/002-artifact-registry/
```

## Complexity Tracking

| Choix                        | Justification                              | Simplification future                      |
| ---------------------------- | ------------------------------------------ | ------------------------------------------ |
| Manifeste de capacité séparé | évite de surcharger les Skills déclaratifs | fusion seulement si les profils convergent |
| Blob/OCI derrière un port    | contenu volumineux et adressé par digest   | démarrer avec Git pour le pilote           |
