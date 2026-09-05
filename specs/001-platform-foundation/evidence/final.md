# État de sortie — Fondation KYA Platform

Date de revue : 2026-09-05
Décision actuelle : **pas encore promotable sur `main`**.

## Critères démontrés

- modèle organisationnel, espaces, affectations datées et refus explicites ;
- publication gouvernée d'un Skill de référence ;
- recherche filtrée avant divulgation et contrats Registry MCP ;
- KYA Platform enregistrée comme premier système réel, limitée aux données du Hub ;
- références de secrets, identité Infisical et rotation ;
- adapter Coolify, previews Neon et déploiement sur `dev` ;
- audit append-only et reconstitution d'historique ;
- accessibilité critique, mobile 360 px et ressources retardées ;
- notifications dédupliquées, révocation après déprovisionnement et signatures Ed25519 ;
- contrôles de charge, sécurité conteneur et SBOM ;
- bundle de sauvegarde chiffré, vérifié et restauré au niveau format.

## Critères encore ouverts

| Tâche | Reste factuel                                                                   | Dépendance                                                       |
| ----- | ------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| T047  | Brancher install → update → rollback à Neon/OpenFGA et l'exécuter par UI et MCP | Backend de distribution persistant et auth utilisateur réelle    |
| T064  | Comparer le même déploiement sur Dokploy et Coolify                             | Instance Dokploy avec identifiants limités                       |
| T078  | Restaurer réellement Postgres et un store OpenFGA isolés                        | URL Neon directe de reprise et instance OpenFGA                  |
| T079  | Rejouer le quickstart complet                                                   | T047, T064 et T078                                               |
| T080  | Protéger `main` et `dev`                                                        | GitHub Pro/Team ou dépôt public ; deuxième approbateur conseillé |
| T082  | Promouvoir `dev` vers `main` et taguer                                          | Tous les critères de sortie précédents                           |

## Validation courante

```text
Backend : 215 tests réussis, couverture 90,83 %
Web : 13 tests unitaires, typage et build réussis
E2E : 3 parcours Playwright réussis
CI, preview, sécurité, images et SBOM : réussis sur dev au jalon v0.1.0-dev.9
```

La fondation est solide pour poursuivre sur `dev`. Elle n'est pas déclarée production tant que les
preuves d'installation réelle, de reprise fournisseur et de gouvernance GitHub ne sont pas closes.
