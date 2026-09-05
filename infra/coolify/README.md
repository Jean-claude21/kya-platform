# Coolify — contrat d’intégration

Coolify implémente le même contrat de promotion que Dokploy. Il peut être sélectionné pour
les previews ou comme fournisseur principal sans changer le domaine métier.

Variables attendues côté secret manager : `COOLIFY_API_URL`, `COOLIFY_API_TOKEN`,
`COOLIFY_PREVIEW_APP_UUID`, `COOLIFY_STAGING_APP_UUID`, `COOLIFY_PRODUCTION_APP_UUID`.
Ces UUID sont des ressources techniques Coolify ; les périmètres fonctionnels sont
gouvernés par KYA Platform et non par Coolify.
