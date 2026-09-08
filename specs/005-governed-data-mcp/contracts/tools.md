# Contrat public des outils MCP Data

Les champs non déclarés sont refusés. Tous les identifiants de corrélation sont générés par le
serveur. L'unité est toujours extraite du jeton OAuth et ne peut pas être fournie par le modèle.

## Règles de sortie

- `active_unit` rend le périmètre explicite ;
- `correlation_id` permet de retrouver la preuve d'audit ;
- `has_more` empêche de faire croire qu'une liste bornée est exhaustive ;
- `content_digest`, qualité et fraîcheur constituent les preuves utiles à l'IA ;
- `storage_provider`, `container`, `object_key`, `secret_reference` et URL signées sont interdits.

## Déclenchement d'ingestion

`start_ingestion(pipeline_key, idempotency_key, confirmation)` crée ou retrouve une exécution
durable. Il ne lance pas du code arbitraire dans le processus MCP et ne donne aucun accès aux clés
du connecteur. La future file de workers consommera l'événement outbox associé.
