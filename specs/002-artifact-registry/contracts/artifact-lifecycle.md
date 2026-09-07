# Contrat — cycle de vie des installations

## Principes

- Une installation désigne toujours une release publiée exacte et son digest.
- Une mise à jour ne devient officielle qu'après reçu du client ayant exécuté le plan.
- La release précédente devient automatiquement la seule cible de rollback immédiat.
- Suspension et reprise sont réversibles ; révocation est terminale.
- Chaque mutation exige confirmation, autorisation KYA, acteur UUID et contrôle de révision.
- Chaque commande persistante produit historique append-only, opération et événement outbox dans
  la même transaction Neon.

## Séquence de mise à jour

1. `list_updates(installation_id)` calcule la release publiée la plus récente compatible.
2. Le client appelle `request_install` sur cette release pour obtenir le plan signé et
   déterministe destiné à son environnement.
3. `request_update` vérifie l'installation et crée une opération idempotente `accepted`.
4. Le client télécharge, vérifie, prépare et active localement selon le plan.
5. `confirm_update` vérifie acteur, signature, digest, compatibilité, état et révision attendue.
6. Neon épingle la nouvelle release, conserve la précédente et marque l'opération `succeeded`.

Une répétition de clé d'idempotence avec une charge différente est refusée. Une confirmation
concurrente avec une révision dépassée est refusée sans écriture partielle.

## Gestion

`manage_installation` accepte `suspend`, `resume`, `revoke` et `rollback`. Un rollback ne peut viser
qu'une release de rollback encore publiée. Une installation révoquée ne peut être reprise.
