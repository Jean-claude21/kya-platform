# KYA Platform

KYA Platform est le plan de contrôle du patrimoine numérique de KYA-Energy Group. La plateforme
référence, gouverne, partage, publie et audite les systèmes, applications, API, produits de données,
serveurs MCP, outils MCP, Skills, templates, modèles et standards de l'entreprise.

Le projet suit une démarche Spec-Driven Development avec GitHub Spec Kit. La constitution du projet
est la source normative ; chaque fonctionnalité possède ensuite une spécification, un plan, des
tâches, des contrôles de cohérence et des preuves de validation avant sa mise en production.

## Branches

- `main` : versions stables et publiables ;
- `dev` : intégration des fonctionnalités validées ;
- `feat-xxx` : développement isolé d'une fonctionnalité, créé depuis `dev` puis fusionné par Pull
  Request vers `dev` ;
- la promotion de `dev` vers `main` passe par une Pull Request et les validations de livraison.

Chaque commit accepté sur `main` reçoit un tag SemVer annoté et immuable. Sur `dev`, les tags de
préversion `vX.Y.Z-dev.N` sont réservés aux jalons réellement déployables.

Les commits directs sur `main` et `dev` seront interdits dès que les protections du dépôt seront
configurées.

## Spec Kit

Workflow attendu pour chaque fonctionnalité :

```text
constitution → specify → clarify → plan → tasks → analyze → implement → converge
```

Les intégrations Codex et Claude sont installées dans le dépôt afin que les agents partagent les
mêmes règles et artefacts.

## État

Le projet est en phase de spécification de sa fondation. Aucun composant n'est considéré comme
opérationnel avant qu'un cas réel ait franchi son cycle complet de validation.
