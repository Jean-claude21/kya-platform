# Validation — Évaluation automatique des veilles

Date : 2026-09-08

## Qualité

- 532 tests réussis ;
- couverture Python : 90,04 % ;
- Ruff : réussi ;
- mypy : réussi sur 145 fichiers ;
- contrôle d'autorisation OpenFGA : réussi ;
- images conteneurs construites, analysées et SBOM générés.

## Livraison

- pull request d'implémentation : `#46` ;
- branche cible : `dev` ;
- commit fusionné : `0edb9f48ddaf2afec0e63d0940abf52777211e06` ;
- application interne : `kya-platform-web-capture-worker` ;
- statut après déploiement : `running:unknown`, attendu pour un worker sans endpoint HTTP ;
- le commit configuré dans Coolify correspond exactement au commit fusionné.

## Contrat vérifié

Le worker consomme désormais deux événements explicitement autorisés :

1. `kya.data.run.started.v1` pour matérialiser un snapshot ;
2. `kya.data.run.completed.v1` pour évaluer les veilles actives de l'unité.

Le pilote utilisateur reste volontairement ouvert : la première veille doit être créée via MCP
par un utilisateur authentifié afin que l'attribution et les autorisations réelles soient prouvées.
