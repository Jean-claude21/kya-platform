# Modèle de données — Fondation KYA Platform

## Conventions

- Identifiants internes UUIDv7 ; clés publiques stables et non réutilisables.
- Dates en UTC, affichées selon le fuseau de l'utilisateur.
- `valid_from`/`valid_until` décrivent la réalité métier ; `created_at`/`superseded_at`
  conservent l'historique enregistré.
- Suppression logique pour les objets référencés ; événements d'audit append-only.
- Chaque ligne métier porte `created_by`, et les mutations sensibles une corrélation.
- Les domaines possèdent leurs tables ; les références inter-domaines passent par identifiant public.

## Organisation

### OrganizationalUnitType

`id`, `key`, `label`, `allowed_parent_types`, `is_temporary`, `status`.

Types initiaux : Groupe, pays, entité, agence, Direction, département, équipe, programme,
projet, communauté. La liste est extensible sans migration du modèle principal.

### OrganizationalUnit

`id`, `key`, `type_id`, `name`, `legal_name?`, `country_code?`, `status`, période de validité.

### OrganizationalUnitRelation

`parent_unit_id`, `child_unit_id`, `relation_type`, période de validité. Le graphe interdit les
cycles pour les relations hiérarchiques, mais autorise plusieurs rattachements transversaux.

### Position et PositionAssignment

Un `Position` décrit une fonction dans une unité. Une `PositionAssignment` relie une personne à
un poste avec type, quotité éventuelle, responsable, délégation et période. Deux affectations
peuvent coexister ; aucune permission n'est déduite d'un intitulé libre.

## Identités et espaces

### Principal

Représente `person`, `service`, `agent` ou `group`. Champs : `id`, `type`, `status`,
`display_name`, `owner_principal_id?`, `valid_until?`.

### ExternalIdentity

`principal_id`, `issuer`, `subject`, `provider`, `last_verified_at`. Le couple issuer/subject est
unique. L'adresse électronique n'est jamais une clé d'identité.

### Workspace

`id`, `key`, `name`, `kind`, `owner_unit_id?`, `classification`, `visibility`, `status`, période.
Un espace peut relier plusieurs unités et projets.

### WorkspaceRelation

Relie principal, groupe ou unité à l'espace : `owner`, `manager`, `contributor`, `member`, `guest`,
`viewer`. La relation peut expirer et être interdite explicitement.

## Autorisation

### Permission

Action atomique sur un type de ressource, par exemple `artifact.read`, `artifact.publish`,
`secret.use`, `deployment.promote`. Elle est versionnée et ne contient pas de périmètre.

### RoleDefinition et RolePermission

Un rôle nomme un ensemble de permissions. Les rôles système sont immuables par version ; les rôles
KYA personnalisés passent par validation.

### RoleAssignment

Relie principal, rôle, portée, espace éventuel, environnement éventuel, période et délégant. Une
attribution sans portée est invalide sauf rôle système explicitement global.

### ResourceRelation et ExplicitDeny

Relations propriétaire/contributeur/lecteur entre un principal et une ressource. Une interdiction
explicite applicable prévaut sur une permission accordée. Les relations servant aux décisions sont
projetées vers OpenFGA de manière idempotente via l'outbox.

### AuthorizationModelVersion et DecisionEvidence

Le modèle publié possède version, hash, tests et date d'activation. Une preuve de décision contient
principal, action, ressource, contexte, décision, modèle, corrélation et raisons non sensibles.

## Catalogue

### Artifact

`id`, `slug`, `type`, `name`, `summary`, `owner_workspace_id`, `business_owner_id`,
`technical_owner_id`, `classification`, `visibility`, `lifecycle_state`.

Types initiaux : système, application, API, Data Product, serveur MCP, outil MCP, Skill, template,
modèle, Design System, connecteur et politique.

### ArtifactVersion

`artifact_id`, `version`, `source_uri`, `commit_sha`, `content_digest`, `manifest_digest`,
`signature`, `compatibility`, `release_notes`, `published_at?`. Unique par artefact/version ; contenu
immuable après publication.

### ArtifactDependency et Capability

Une dépendance déclare cible ou capacité, plage de versions, caractère requis et motif. Une
capacité possède une clé stable, un contrat, un niveau de risque et un système fournisseur.

### RegisteredSystem et DataAuthority

Le système déclare propriétaires, état, environnements et interfaces. `DataAuthority` relie une
catégorie de données à un système pour une portée et une période ; deux autorités actives et
exclusives ne peuvent se chevaucher. Frappe/ERPNext est une instance de `RegisteredSystem`.

## Publication et distribution

### PublicationRequest, Review et Approval

La demande fige la version candidate et la politique applicable. Les revues conservent contrôle,
preuve et résultat. Une approbation contient décideur, mandat, décision, commentaire, date et
expiration éventuelle. Le demandeur ne peut approuver lorsque la séparation des responsabilités
est exigée.

### Release

Associe version immuable, canal (`internal`, `pilot`, `stable`, `deprecated`), audience, date,
preuves et politique de retrait.

### Installation et UpdateAssessment

Une installation relie release, bénéficiaire, environnement, état, configuration non secrète et
version saine précédente. L'évaluation quotidienne conserve version actuelle, versions candidates,
compatibilité, risque, décision et prochaine action.

## Secrets et déploiement

### SecretReference

`id`, `provider`, `external_path`, `owner_workspace_id`, `purpose`, `environment_id`,
`classification`, `rotation_policy`, `expires_at?`, `status`. Aucune valeur secrète n'est admise.

### Environment et DeploymentTarget

Un environnement possède type, criticité, politique et source de données. Une cible associe une
application, un environnement, un fournisseur de déploiement et des références de configuration.
Une seule cible primaire active existe par application/environnement.

### Deployment

`target_id`, `release_id`, `artifact_digest`, `requested_by`, `approved_by?`, `status`, horodatages,
URL de preuve, version précédente et résultat de rollback. Le même digest traverse les promotions.

## Fiabilité

### AuditEvent

Événement append-only : identifiant, temps, acteur, session/service, action, cible, portée,
environnement, décision, résultat, corrélation, causalité et métadonnées nettoyées.

### OutboxEvent et IdempotencyRecord

L'outbox rend fiables les projections OpenFGA, notifications et synchronisations. Toute commande
externe accepte une clé d'idempotence ; une répétition retourne le résultat antérieur sans doubler
l'action.

## Transitions principales

```text
Artifact: draft → prototype → candidate → validating → approved → published
          published → suspended → published
          published → deprecated → retired

Installation: requested → validating → approved → applying → active
              applying → failed → rolling_back → active|failed

Deployment: requested → checks → approved → deploying → healthy
            deploying|healthy → rollback → rolled_back|failed
```

Toute transition vérifie la version attendue pour empêcher les mises à jour concurrentes perdues.
