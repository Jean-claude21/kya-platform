# Contrat Registry MCP

Transport distant : Streamable HTTP protégé par OAuth. L'identité et les scopes du jeton sont
nécessaires mais insuffisants : chaque outil appelle aussi l'autorisation KYA sur sa ressource.

## Outils initiaux

- `search_catalog(query, types?, workspace?, cursor?)` — lecture filtrée par droits.
- `get_artifact(artifact_id, version?)` — métadonnées visibles, jamais de secret.
- `list_updates(environment?, installation_id?)` — mises à jour compatibles autorisées.
- `request_install(release_id, target, idempotency_key)` — crée une demande, sans exécution cachée.
- `request_update(installation_id, release_id, idempotency_key)` — applique la politique de revue.
- `get_operation(operation_id)` — état et preuve accessibles au demandeur.
- `publish_candidate(artifact_id, version, evidence)` — réservé aux mainteneurs autorisés.

Chaque outil déclare schémas stricts d'entrée/sortie, scopes, niveau de risque, caractère lecture ou
écriture, idempotence, confirmation et erreurs stables. La liste d'outils peut être réduite selon le
demandeur avant exposition. Un Skill est retourné comme artefact à charger par le client IA ; il
n'est jamais exécuté comme un outil.
