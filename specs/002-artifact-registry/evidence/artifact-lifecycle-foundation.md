# Preuve intermédiaire T017 — fondation du cycle de vie

## Invariants livrés

- une release suspendue ou révoquée est refusée pour toute nouvelle installation ou mise à jour ;
- seule une installation active peut être mise à jour ;
- une révocation est terminale, tandis qu'une suspension peut être reprise ;
- le rollback ne cible que la dernière release connue comme saine ;
- chaque transition incrémente une révision et produit un événement outbox ;
- les transitions répétées sont idempotentes au niveau du domaine.

## Projection Neon appliquée

- `catalog.installation` conserve la cible, le profil, la release active, la release de rollback,
  l'état et la révision ;
- `catalog.installation_history` est append-only et ordonné par installation ;
- `catalog.distribution_operation` lie acteur et clé d'idempotence et conserve l'issue ;
- les releases et historiques restent référencés avec suppression restrictive.

La migration `20260907_0009` a été appliquée sur la branche Neon `dev` et confirmée comme
révision `head`. Le Registry MCP fournit :

- `list_updates`, limité à une installation explicitement autorisée ;
- `request_update`, qui prépare une opération idempotente sans prétendre que le poste est modifié ;
- `confirm_update`, qui applique atomiquement le reçu client et conserve la release de rollback ;
- `manage_installation` pour suspendre, reprendre, révoquer ou restaurer avec révision optimiste ;
- `get_operation` pour relire l'issue persistée ;
- `confirm_installation` pour convertir un plan exécuté localement en installation officielle.

Les écritures d'installation et de mise à jour restent biphasées : KYA prépare et contrôle, le
client consent et exécute, puis KYA ne change l'état officiel qu'après vérification du reçu.

Les installations et opérations ne créent pas un univers d'autorisation parallèle : leur cible
`workspace:*` est résolue côté serveur avant chaque contrôle OpenFGA. La lecture dépend de
`can_view`, l'installation et la mise à jour de `can_edit`, et les actions sensibles de
`can_manage` sur l'espace concerné.

## Validation

- Ruff : conforme ;
- mypy strict : conforme sur 97 fichiers source ;
- pytest : 355 tests réussis, couverture globale 90,03 % ;
- contrats Markdown : conformes à Prettier ;
- recherche de secrets connus dans les fichiers suivis : aucun résultat.
