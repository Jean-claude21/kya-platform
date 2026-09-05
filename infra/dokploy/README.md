# Dokploy — contrat d’intégration

Dokploy est un fournisseur d’exécution compatible avec le port `DeploymentProvider`.
Le workflow GitHub lui transmet une image immuable (`IMAGE_DIGEST`), jamais un tag mutable.
Les URLs et jetons sont injectés par l’environnement d’exécution ; aucune clé ne doit être
commise dans Git. La promotion production exige une PR `dev → main` et un tag SemVer.

Variables attendues côté secret manager : `DOKPLOY_API_URL`, `DOKPLOY_API_TOKEN`,
`DOKPLOY_PROJECT_ID`, `DOKPLOY_PREVIEW_APP_ID`, `DOKPLOY_STAGING_APP_ID`,
`DOKPLOY_PRODUCTION_APP_ID`. Le `DOKPLOY_PROJECT_ID` est un regroupement technique
Dokploy ; il ne limite pas le nombre d'espaces, de pays ou d'équipes KYA.
