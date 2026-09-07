# Tasks: Registre des artefacts KYA

## Phase 1 — Contrats et domaine

- [x] T001 Étendre le contrat de manifeste dans `apps/backend/src/kya_platform/contracts/`.
- [x] T002 Ajouter inventaire, classification et manifeste de capacité avec tests de contrat.
- [ ] T003 Renforcer les invariants du domaine catalogue et les transitions.

## Phase 2 — Persistance Neon

- [x] T004 Ajouter les modèles SQLAlchemy catalogue et la migration Alembic immuable.
- [x] T005 Implémenter repository et transaction catalogue.
- [ ] T006 Tester contraintes, concurrence et immutabilité d'une version publiée.

## Phase 3 — Première tranche verticale Skill

- [x] T007 Ajouter création et lecture d'artefact par API avec OpenFGA.
- [x] T008 Valider sans exécution un Skill multi-fichiers réel.
- [x] T009 Persister artefact, version, inventaire et événement outbox atomiquement.
- [x] T010 Prouver refus des traversées, archives ambiguës, secrets et limites dépassées.

## Phase 4 — Registry MCP

- [x] T011 Raccorder le backend de registre à Neon.
- [x] T012 Monter le Registry MCP OAuth séparément du MCP public de diagnostic.
- [x] T013 Filtrer outils et résultats avant divulgation selon OAuth + OpenFGA.
- [ ] T014 Tester Claude/ChatGPT avec recherche et détail d'un Skill autorisé.

## Phase 5 — Publication et distribution

- [x] T015 Raccorder attestations, séparation des rôles et signature à la persistance.
- [ ] T016 Produire un plan d'installation Codex, Claude Code et portable zip.
- [ ] T017 Implémenter mises à jour, suspension, révocation et rollback.

## Phase 6 — Pilote et clôture

- [ ] T018 Publier le premier Skill métier KYA complet avec preuves.
- [ ] T019 Exécuter sécurité, performance, accessibilité et reprise.
- [ ] T020 Fusionner dans `dev`, taguer, déployer et documenter la démonstration.
