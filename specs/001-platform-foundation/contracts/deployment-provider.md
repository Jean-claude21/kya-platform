# Contrat DeploymentProvider

Chaque adapter Dokploy ou Coolify doit implémenter les mêmes opérations :

- `createPreview(change, artifactDigest, environmentRefs)` ;
- `getDeploymentStatus(providerDeploymentId)` ;
- `promote(release, target, approvalEvidence)` ;
- `rollback(target, previousHealthyDigest)` ;
- `destroyPreview(providerDeploymentId)` ;
- `verifyCapabilities()`.

Invariants : idempotence par commande, digest obligatoire, aucun secret dans les réponses, URL de
preuve, délais bornés, journal corrélé et état normalisé. Un fournisseur ne décide jamais si une
promotion est autorisée ; il exécute une décision déjà validée par KYA Platform.

États normalisés : `queued`, `building`, `deploying`, `healthy`, `degraded`, `failed`,
`rolling_back`, `rolled_back`, `deleted`.

La suite de conformité teste preview, isolation des secrets, mise à jour, fermeture de PR,
promotion du même digest, panne simulée, rollback et suppression des ressources temporaires.
