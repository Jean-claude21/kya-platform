# Coolify — contrat d’intégration

Coolify implémente le même contrat de promotion que Dokploy. Il peut être sélectionné pour
les previews ou comme fournisseur principal sans changer le domaine métier.

Les processus sont déployés séparément :

- `kya-platform-web` expose l'interface utilisateur ;
- `kya-platform-backend` expose l'API et MCP ;
- `kya-platform-web-capture-worker` consomme uniquement les événements
  `kya.data.run.started.v1` et ne possède aucun domaine public.

Le worker reçoit sa connexion à la base et son identité Infisical. Les secrets du stockage objet
restent dans Infisical et sont résolus au démarrage ; ils ne sont pas recopiés dans Coolify.

Variables attendues côté secret manager : `COOLIFY_API_URL`, `COOLIFY_API_TOKEN`,
`COOLIFY_PROJECT_UUID`, `COOLIFY_SERVER_UUID`, `COOLIFY_WEB_APPLICATION_NAME` et
`COOLIFY_BACKEND_APPLICATION_NAME`. Les applications sont découvertes par leur nom dans
l'environnement cible ; leurs identifiants internes sont retournés et conservés par l'adapter.
