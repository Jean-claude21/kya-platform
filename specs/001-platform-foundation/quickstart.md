# Quickstart de validation — Fondation KYA Platform

Ce guide définit les preuves attendues ; les commandes exactes seront ajoutées avec
l'implémentation sans affaiblir les résultats.

## Scénario de référence

1. Créer Direction A, équipe A1, projet transversal P et espace de stagiaires expirant.
2. Affecter Alice à A1, Bob à une autre Direction, Chloé à P et Sam comme stagiaire temporaire.
3. Publier un Skill de référence depuis A1 avec le template officiel et deux approbateurs.
4. Enregistrer Frappe comme système et le déclarer autoritaire pour une catégorie pilote.
5. Vérifier qu'Alice et Chloé découvrent le Skill selon le partage, que Bob ne peut ni le voir ni
   l'énumérer, et que Sam perd son accès à l'expiration.
6. Installer le Skill via l'interface puis demander son état via le Registry MCP.
7. Publier une nouvelle version, exécuter la vérification quotidienne, mettre à jour puis revenir à
   la version saine précédente.
8. Reconstituer toutes les actions depuis l'audit sans révéler la valeur d'un secret.

## Déploiement factuel

Exécuter la même application de démonstration successivement contre les adapters Dokploy et Coolify :

- branche `feat-xxx` et Pull Request vers `dev` ;
- branche Neon de preview avec données synthétiques ;
- secrets de preview distincts ;
- fermeture de PR et nettoyage ;
- promotion de `dev` vers `main` ;
- tag SemVer annoté ;
- promotion du même digest ;
- panne simulée et rollback.

Le rapport compare temps de mise en place, durée de déploiement, isolation, preuve GitHub, gestion
des secrets, observabilité, rollback, nettoyage, API et charge d'exploitation. Le fournisseur
primaire n'est choisi qu'après ce rapport.

## Critères de sortie

- Tous les scénarios P1 et P2 réussissent, y compris les tests négatifs d'autorisation.
- Le manifeste de référence valide son schéma et échoue pour digest, propriétaire ou version absent.
- Aucun secret ou jeton n'apparaît dans dépôt, base du Hub, logs, résultats MCP ou captures de test.
- Les opérations répétées avec la même clé d'idempotence ne produisent aucun doublon.
- Le retrait d'une affectation coupe les accès dans le délai défini par la spécification.
- Le rollback restaure la dernière version saine et conserve la preuve de l'échec.
