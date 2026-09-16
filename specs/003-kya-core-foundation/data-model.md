# Modèle de données — KYA Core v0.1

## Identité conceptuelle

`Party` décrit le monde réel. `Principal` décrit un acteur numérique. Une personne peut exister
avant d'avoir un compte et son historique reste intact après désactivation du compte.

## Tables du schéma `core`

- `party` : personne ou organisation, nom d'affichage, statut, version.
- `person_profile` : noms structurés d'une partie de type personne.
- `work_relationship` : relation temporelle employé, stagiaire, prestataire ou consultant.
- `organizational_unit_type` : type extensible et règles de parents permises.
- `organizational_unit` : unité stable et période d'activité.
- `organizational_unit_relation` : hiérarchie ou relation transversale datée.
- `position` : poste rattaché à une unité et daté.
- `position_assignment` : affectation d'une personne à un poste, datée et historisée.
- `client_account` : statut commercial d'une partie dans un périmètre KYA.
- `contact_point` : moyen de contact d'une partie, classifié et daté.
- `project` : projet KYA, unité responsable, client éventuel et cycle de vie.
- `site` : lieu stable appartenant à une partie et administré dans un périmètre.
- `project_site` : association entre projets et sites.
- `external_reference` : correspondance vers un système enregistré.

## Invariants

- `valid_until > valid_from` lorsque la fin existe.
- aucune unité ou affectation ne se rattache à elle-même.
- une partie a exactement un genre structurel (`person` ou `organization`).
- les informations de stage sont dans `work_relationship`, jamais dans `party`.
- les clés d'unité, client, projet et site ne sont jamais réutilisées.
- une référence `(system_key, entity_type, external_type, external_id)` est unique.
- `version` commence à 1 et sert au contrôle de concurrence optimiste.
