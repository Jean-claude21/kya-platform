# Preuves US6 — déploiement et previews

## Validation locale

- Suite backend : 175 tests réussis, couverture 90,49 %.
- Analyse statique : Ruff et mypy réussis.
- Contrat Coolify : découverte par projet, environnement et nom logique ; déploiement,
  état normalisé et rollback testés avec transport HTTP contrôlé.
- Contrat Neon : création idempotente et suppression récupérable testées.

## Validation fournisseurs du 5 septembre 2026

- Authentification Neon API réussie sur le projet configuré.
- Branche `preview/pr-999999` créée par l'adapter puis supprimée sans suppression définitive.
- Branches persistantes `dev` et `staging` créées avec un endpoint en lecture-écriture.
- Authentification Coolify Cloud réussie sur `https://app.coolify.io/api/v1`.
- Projet `KYA Platform` et environnements `dev`, `staging`, `production` présents.
- Dépôt privé `Jean-claude21/kya-platform` visible par la GitHub App Coolify.
- Applications Web et Backend provisionnées dans les trois environnements, sans lancement
  prématuré avant publication du code et configuration des secrets.

## Limite du benchmark

Le scénario Coolify réel est prêt. Le benchmark identique avec Dokploy reste ouvert tant que
les paramètres d'une instance Dokploy ne sont pas fournis. Aucun choix définitif entre les deux
fournisseurs n'est déclaré avant cette mesure.
