# Contrat initial — Business API KYA Core

Base : `/api/v1/core`

Authentification : Bearer Neon Auth

Contexte obligatoire : `X-KYA-Unit-ID`
Écriture rejouable : `Idempotency-Key` pour les commandes exposées

## Organisation

- `GET /organization/{unit_key}`
- `GET /organization/{unit_key}/children?at=&limit=`
- `POST /organization/{unit_key}/children`

## Clients

- `GET /organization/{unit_key}/clients?limit=`
- `POST /organization/{unit_key}/clients`
- `GET /organization/{unit_key}/clients/{client_id}`

## Projets

- `GET /organization/{unit_key}/projects?limit=`
- `POST /organization/{unit_key}/projects`
- `GET /organization/{unit_key}/projects/{project_id}`

## Autorisations

- lecture : `can_view` sur `org_unit:{unit_key}` ;
- écriture : `can_manage` sur `org_unit:{unit_key}` ;
- le dépôt reçoit toujours l'identifiant de périmètre et ne retourne jamais un enregistrement
  appartenant à un autre périmètre, même après une décision d'accès positive.

## Événements initiaux

- `kya.core.organization_unit.created.v1`
- `kya.core.client.created.v1`
- `kya.core.project.created.v1`

Chaque événement contient `event_id`, `occurred_at`, `aggregate_id`, `scope_unit_id`, `actor_id`,
`correlation_id` et une charge minimale sans secret ni donnée de contact.

## Évolution compatible prévue

Les curseurs opaques et filtres `query`/`status` seront ajoutés lorsque la volumétrie ou la première
application l'exigera. Ils sont volontairement absents de v0.1 afin de ne pas figer prématurément
une stratégie de recherche ; toutes les listes sont néanmoins bornées à 100 éléments.
