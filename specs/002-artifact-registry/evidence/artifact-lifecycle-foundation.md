# Preuve intermédiaire T017 — fondation du cycle de vie

## Invariants livrés

- une release suspendue ou révoquée est refusée pour toute nouvelle installation ou mise à jour ;
- seule une installation active peut être mise à jour ;
- une révocation est terminale, tandis qu'une suspension peut être reprise ;
- le rollback ne cible que la dernière release connue comme saine ;
- chaque transition incrémente une révision et produit un événement outbox ;
- les transitions répétées sont idempotentes au niveau du domaine.

## Projection Neon préparée

- `catalog.installation` conserve la cible, le profil, la release active, la release de rollback,
  l'état et la révision ;
- `catalog.installation_history` est append-only et ordonné par installation ;
- `catalog.distribution_operation` lie acteur et clé d'idempotence et conserve l'issue ;
- les releases et historiques restent référencés avec suppression restrictive.

La migration `20260907_0009` est validée en génération SQL hors ligne. Le raccordement transactionnel
du repository et des outils MCP reste à réaliser avant de déclarer T017 terminée.
