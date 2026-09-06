# Scellage de l'initialisation du propriétaire de plateforme

## Résultat

Le 6 septembre 2026, l'initialisation du premier propriétaire KYA Platform a été scellée avec
succès sur l'environnement public de validation. La plateforme conserve l'identité propriétaire
déjà enregistrée, mais ne détient plus de code ni d'adresse d'amorçage permettant de rejouer
l'opération.

## Référence livrée

- Branche applicative : `dev`.
- Commit applicatif déployé : `efea1da19c033149f223e65d2d8fd79f2f6a012a`.
- Tag applicatif : `v0.1.0-dev.16`.
- Déploiement backend Coolify : `fhl5szc2kpehlmilwgcpcxcl`, terminé avec succès.

## Vérifications exécutées

1. L'enregistrement durable d'initialisation était à l'état `complete` avant le scellage.
2. Les quatre entrées Coolify d'amorçage ont été supprimées : adresse et empreinte du code,
   chacune dans les périmètres runtime et preview.
3. Le backend a été redéployé après leur suppression.
4. Un nouveau compte de test non privilégié a obtenu `200` sur `/api/v1/account/me` puis `200`
   sur `/api/v1/bootstrap/status` ; le statut est resté `complete` et l'identité non éligible.
5. Le compte de test et sa liaison applicative ont été supprimés après la vérification.
6. Le secret `KYA_PLATFORM_BOOTSTRAP_CLAIM_CODE` a été supprimé du projet Infisical
   `KYA Platform Secrets`, environnement `staging`, chemin `/`.
7. Une lecture Infisical ultérieure du même secret a renvoyé `404`.
8. L'identité machine Infisical `kya-platform-preview` a été ramenée du rôle `Admin` au rôle
   permanent `Viewer` après la suppression, puis son rôle a été relu par l'API.
9. Après le scellage et cette réduction de privilèges, l'application Web et les routes
   `/api/v1/health/live` et
   `/api/v1/health/ready` ont toutes répondu `200`.

## Contrôles de qualité associés

- Suite backend : 242 tests réussis.
- Couverture backend : 90,18 %.
- Ruff et MyPy : réussis.
- Contrôles GitHub : qualité, validation, dépendances/secrets/configuration, conteneurs/SBOM,
  modèle d'autorisation, données de preview et politique de branches réussis.

## Garanties et limites

- Le scellage ne retire aucun droit au propriétaire déjà établi.
- OpenFGA demeure l'autorité pour les décisions d'accès ; Neon conserve l'état durable de
  l'initialisation.
- Sans enregistrement durable `complete`, une plateforme dépourvue de configuration
  d'amorçage échoue fermée avec un état indisponible ; elle ne rouvre jamais automatiquement
  l'initialisation.
- L'identité machine Infisical utilisée pour la validation est limitée à la lecture ; les clés
  exposées pendant la mise en place doivent être renouvelées séparément.
