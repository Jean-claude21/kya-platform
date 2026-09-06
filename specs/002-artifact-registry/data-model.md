# Modèle de données — Registre des artefacts

## Agrégats

### Artifact

`id`, `registry_id`, `slug`, `type`, `name`, `summary`, `owner_workspace_id`,
`business_owner_id`, `technical_owner_id`, `visibility`, `lifecycle`, horodatages.

Contrainte : unicité `(registry_id, slug)` et identité publique `kya:{type}:{slug}`.

### ArtifactVersion

`id`, `artifact_id`, `version`, `status`, `source_repository`, `source_commit`, `source_path`,
`content_digest`, `manifest_digest`, `package_size`, `file_count`, `has_executable_content`,
`risk`, `created_by`, horodatages.

Contrainte : unicité `(artifact_id, version)` ; après publication, les champs d'intégrité et de
provenance sont immuables.

### PackageFile

`version_id`, `path`, `media_type`, `size`, `sha256`, `kind`, `executable`, `mode`.

Contrainte : chemin relatif NFC, séparateur `/`, sans `.`/`..`, NUL, doublon insensible à la casse,
ni préfixe réservé. La somme des tailles et le nombre d'entrées sont bornés.

### CapabilityDeclaration

`version_id`, `runtime`, `entrypoints`, `commands`, `network_policy`, `filesystem_policy`,
`secret_references`, `requested_permissions`, `resource_limits`.

Requis si un fichier est exécutable, contient une macro ou si le manifeste demande une capacité.

### ArtifactDependency

`version_id`, `dependency_artifact_id`, `version_range`, `optional`, `purpose`.

### Attestation

`id`, `version_id`, `kind`, `predicate_type`, `digest`, `issuer`, `subject_digest`, `result`,
`valid_from`, `valid_until`, `evidence_uri`.

### Release

`id`, `version_id`, `digest`, `signature`, `storage_locator`, `status`, `published_at`,
`suspended_at`, `revoked_at`, `reason`.

### InstallationTarget et Installation

La cible déclare `profile` (`codex`, `claude-code`, `portable-zip`), plateforme, versions et
capacités. L'installation épingle une release, conserve l'état, la dernière vérification et la
release de rollback.

## Règles de suppression

- Un Artifact publié n'est jamais supprimé physiquement ; il est retiré.
- Une version non publiée sans référence peut être abandonnée selon la rétention.
- Une Release révoquée reste dans l'audit et l'historique des installations.
- Un fichier n'est pas stocké dans PostgreSQL ; seule sa métadonnée et son locator sont conservés.
