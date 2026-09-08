# Contrat MCP — `get_ingestion_run`

## Entrée

```json
{ "run_id": "uuid" }
```

## Sortie

```json
{
  "run_id": "uuid",
  "pipeline_key": "kya-institutional-web-capture",
  "status": "completed",
  "started_at": "date-time",
  "completed_at": "date-time|null",
  "error_code": null,
  "snapshot": {
    "snapshot_id": "uuid",
    "contract_id": "uuid",
    "content_digest": "sha256",
    "media_type": "application/vnd.kya.web-capture+json",
    "observed_at": "date-time",
    "row_count": 25,
    "byte_size": 4120857
  },
  "quality_results": [
    { "rule_key": "pages-present", "status": "passed", "observed": { "count": 25 } }
  ],
  "active_unit": "direction-cvsi",
  "correlation_id": "uuid"
}
```

Les références internes de stockage sont volontairement absentes.
