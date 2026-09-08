# Modèle de données — KYA Intelligence v0.1

## `intelligence.watch`

| Champ | Rôle |
|---|---|
| `id`, `key` | identité interne et clé stable dans l'unité |
| `owner_unit_id` | frontière d'autorisation et de partage |
| `created_by` | responsabilité humaine |
| `query` | expression lexicale déterministe |
| `asset_keys` | filtre optionnel sur les actifs gouvernés |
| `status` | `active` ou `paused` |
| `revision` | concurrence optimiste |

Unicité : `(owner_unit_id, key)`.

## `intelligence.signal`

| Champ | Rôle |
|---|---|
| `watch_id`, `chunk_id` | origine et déduplication |
| `snapshot_id`, `citation_id` | traçabilité KYA |
| `source_uri`, `title`, `excerpt` | preuve directement exploitable |
| `snapshot_digest`, `page_digest` | vérification d'intégrité |
| `observed_at` | temporalité de la source |
| `status`, `acknowledged_*`, `revision` | traitement opérationnel audité |

Unicité : `(watch_id, chunk_id)`. Les champs de preuve sont immuables après création.

