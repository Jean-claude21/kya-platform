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

## Pilote MCP utilisateur

Le pilote a été exécuté depuis un client IA connecté à `KYA-Platform`, sous l'identité réelle de
l'utilisateur et dans l'unité active `group` :

- veille créée : `veille-solaire`, nom `Marché solaire`, statut `active`, révision 1 ;
- requête : `solaire` ;
- première évaluation : 16 correspondances et 16 nouveaux signaux ;
- consultation : 16 signaux ouverts, avec extraits, URI sources et citations KYA ;
- corrélation d'évaluation : `01a0828d-6527-748d-a8e9-ec619e701896` ;
- snapshot cité : `01a08109-7647-77ba-8bd0-c35830fb0ff3`.

Une lecture indépendante de Neon a confirmé une veille active, 16 signaux persistés, 16 signaux
ouverts et un snapshot distinct. Le premier corpus provient du site institutionnel KYA : ce pilote
valide donc la veille de cohérence interne. Une veille marché nécessitera des sources externes
gouvernées dédiées.
