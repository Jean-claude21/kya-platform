# Gouvernance du dépôt KYA Platform

Date de contrôle : 2026-09-05

## Flux obligatoire

- `feat-xxx` part de `dev` et revient vers `dev` par Pull Request ;
- `dev` est la branche d'intégration, avec tags facultatifs `vX.Y.Z-dev.N` sur les jalons
  effectivement déployables ;
- seule `dev` peut ouvrir une Pull Request vers `main` ;
- chaque commit accepté sur `main` reçoit un tag SemVer annoté ;
- aucune branche fonctionnelle ne pousse directement sur `main`.

Les workflows contrôlent déjà le nom et la destination des branches, le lint, le typage, les tests,
le modèle OpenFGA, les secrets, les images de conteneur et les SBOM.

## Propriétaires et approbations

Le dépôt privé possède actuellement un seul administrateur direct : `Jean-claude21`. Il n'existe
donc pas encore deux comptes permettant de démontrer une séparation de responsabilités dans
GitHub. Pour les changements sensibles, la validation fonctionnelle et la validation technique
doivent être deux décisions distinctes dans KYA Platform, même si GitHub ne peut pas encore les
matérialiser avec deux approbateurs.

## Protection GitHub non activable actuellement

L'API GitHub renvoie `403` pour les protections de `main` et `dev` : le plan du dépôt privé doit être
mis à niveau, ou le dépôt rendu public, pour activer cette fonctionnalité. Le dépôt ne doit pas être
rendu public pour contourner cette restriction.

T080 reste donc ouverte. Une fois la fonctionnalité disponible et un second propriétaire nommé :

- interdire les pushes directs et suppressions de `main` ;
- exiger une Pull Request `dev → main`, une approbation indépendante et tous les checks ;
- interdire le contournement administrateur de `main` hors procédure d'urgence auditée ;
- exiger une Pull Request `feat-xxx → dev` et les checks de qualité/sécurité ;
- conserver l'historique linéaire ou les merge commits selon la preuve de release retenue, sans
  squash d'un tag déjà publié.
