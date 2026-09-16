# Contrat HTTP — Source lifecycle v0.1

Préfixe : `/api/v1/data/organization/{unit_key}/flows`

## `POST /`

Crée atomiquement un flux. Requiert `Idempotency-Key` et `can_manage` sur l'unité.

Entrée : clé, nom, source (`kind`, configuration, référence secrète), connecteur (`key`, `version`),
actif (`layer`, classification), contrat et planification facultative.

Sortie `201` : identités et états du flux, sans référence secrète ni emplacement Storage.

## `GET /{flow_key}`

Retourne la projection de santé : états, dernier run, dernier snapshot, prochaine échéance et dernier
résultat de qualité. Requiert `can_view`.

## `POST /{flow_key}/pause` et `POST /{flow_key}/activate`

Mutation atomique avec `Idempotency-Key` et `If-Match` portant la révision courante.

## `PUT /{flow_key}/schedule`

Crée ou remplace la planification par révision optimiste. Une planification désactivée reste lisible.

## Erreurs stables

- `source_flow_conflict` — collision, révision obsolète ou rejeu incohérent ;
- `source_flow_reference_invalid` — unité ou connecteur invalide ;
- `source_flow_invalid_state` — transition impossible ;
- `source_flow_not_found` — flux invisible ou absent.
