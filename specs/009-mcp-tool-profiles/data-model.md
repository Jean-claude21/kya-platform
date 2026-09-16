# Modèle de données

Schéma PostgreSQL : `mcp_control`.

## `tool_definition`

Clé publique immuable, namespace, libellé, scope OAuth, type de cible, relation OpenFGA, risque,
indicateurs de confirmation/idempotence, handler, digests des schémas, état et horodatages. Une
déclaration sans handler actif reste invisible.

## `tool_profile`

Clé, nom, description, nature (`system`, `business`, `personal-template`), unité propriétaire
facultative, état, version, révision optimiste et plafond d'outils. Plafond initial : 24.

## `tool_profile_item`

Clé composée profil/outil, état `enabled|disabled`, ordre stable, auteur et date. Tout `disabled`
applicable gagne sur les activations.

## `tool_profile_assignment`

Profil, sujet (`user|team|role|org_unit`), clé du sujet, contexte d'unité facultatif, fenêtre de
validité, auteur et révocation logique.

## `user_tool_preference`

Principal, unité active, client OAuth facultatif, outil et état `disabled`. La suppression restaure
l'héritage. Aucun jeton ni secret n'est enregistré.

## Révision effective

La révision retournée est un digest stable des révisions de définitions, profils, affectations et
préférences utilisées. Elle permet l'observation et le cache, pas l'autorisation.
