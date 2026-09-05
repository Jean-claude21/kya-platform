# Coolify — contrat d’intégration

Coolify implémente le même contrat de promotion que Dokploy. Il peut être sélectionné pour
les previews ou comme fournisseur principal sans changer le domaine métier.

Variables attendues côté secret manager : `COOLIFY_API_URL`, `COOLIFY_API_TOKEN`,
`COOLIFY_PROJECT_UUID`, `COOLIFY_SERVER_UUID`, `COOLIFY_WEB_APPLICATION_NAME` et
`COOLIFY_BACKEND_APPLICATION_NAME`. Les applications sont découvertes par leur nom dans
l'environnement cible ; leurs identifiants internes sont retournés et conservés par l'adapter.
