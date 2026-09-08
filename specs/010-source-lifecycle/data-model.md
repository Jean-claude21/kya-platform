# Modèle de données — Cycle de vie des sources

## SourceFlow

Projection non dupliquée composée de `DataSource`, `DataAsset`, `DataContract` et `DataPipeline`.
Les quatre clés partagent un préfixe métier stable mais gardent leurs identités et contrats propres.

## IngestionSchedule

| Champ                      | Règle                                     |
| -------------------------- | ----------------------------------------- |
| `id`                       | UUID serveur                              |
| `pipeline_id`              | pipeline unique                           |
| `interval_minutes`         | entier entre 15 et 43 200                 |
| `next_run_at`              | instant UTC conscient                     |
| `enabled`                  | désactivation sans suppression            |
| `revision`                 | entier positif pour concurrence optimiste |
| `last_claimed_at`          | dernière échéance logique réclamée        |
| `created_by`, `updated_by` | principaux KYA                            |

Contrainte centrale : une seule planification par pipeline. La réclamation verrouille la ligne,
avance `next_run_at` avant de créer le run et utilise une clé d'idempotence dérivée de l'échéance.

## Transitions

```text
draft → active ↔ paused → deprecated → retired
```

La v0.1 expose `active ↔ paused`. Les autres transitions restent réservées aux futures politiques
de publication et de rétention.
