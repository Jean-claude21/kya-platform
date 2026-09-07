# Contrat Business API — Data Foundation v0.1

Préfixe : `/api/v1/data/organization/{unit_key}`.

Toutes les routes exigent un jeton OAuth valide et une autorisation OpenFGA sur
`org_unit:{unit_key}`. Les mutations exigent aussi `Idempotency-Key` (16 à 200 caractères).

| Méthode | Route                           | Permission   | Résultat                         |
| ------- | ------------------------------- | ------------ | -------------------------------- |
| `GET`   | `/sources`                      | `can_view`   | sources de l'unité               |
| `POST`  | `/sources`                      | `can_manage` | source enregistrée               |
| `GET`   | `/assets`                       | `can_view`   | actifs de l'unité                |
| `POST`  | `/assets`                       | `can_manage` | actif enregistré                 |
| `POST`  | `/assets/{asset_id}/contracts`  | `can_manage` | contrat immuable publié          |
| `POST`  | `/pipelines`                    | `can_manage` | pipeline épinglé à un connecteur |
| `POST`  | `/pipelines/{pipeline_id}/runs` | `can_manage` | exécution démarrée               |
| `POST`  | `/runs/{run_id}/complete`       | `can_manage` | snapshot et preuves enregistrés  |
| `POST`  | `/runs/{run_id}/fail`           | `can_manage` | échec terminal enregistré        |
| `GET`   | `/assets/{asset_key}/snapshots` | `can_view`   | historique des snapshots         |

## Règles de protocole

- Le serveur génère les UUIDv7, le digest canonique du contrat et les horodatages d'exécution.
- Le client ne peut pas réécrire le pipeline ni l'heure de départ lors de la clôture.
- `storage.object_key` est une clé d'objet, jamais une URL signée.
- `secret_reference` est une référence Infisical opaque, jamais une valeur secrète.
- Une fin réussie transporte snapshot, résultats qualité et snapshots d'entrée éventuels dans
  une seule transaction.
