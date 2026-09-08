# Contrat HTTP — KYA Intelligence v0.1

Préfixe : `/api/v1/intelligence/organization/{unit_key}`.

| Méthode | Route                              | Autorisation                     |
| ------- | ---------------------------------- | -------------------------------- |
| `POST`  | `/watches`                         | `org_unit:{unit_key}#can_manage` |
| `GET`   | `/watches`                         | `org_unit:{unit_key}#can_view`   |
| `POST`  | `/watches/{watch_key}/evaluate`    | `can_manage`                     |
| `GET`   | `/watches/{watch_key}/signals`     | `can_view`                       |
| `POST`  | `/signals/{signal_id}/acknowledge` | `can_manage`                     |

Toutes les mutations exigent `Idempotency-Key`. L'acquittement exige également `If-Match`.

## Outils MCP

- `list_intelligence_watches`
- `create_intelligence_watch`
- `evaluate_intelligence_watch`
- `list_intelligence_signals`
- `acknowledge_intelligence_signal`

Les lectures utilisent `data:read`. Les mutations utilisent `data:ingest`, une confirmation
explicite et une clé d'idempotence. Les profils peuvent masquer individuellement chaque outil.
