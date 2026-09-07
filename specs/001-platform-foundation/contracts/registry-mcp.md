# Contrat Registry MCP

Transport distant : MCP `2026-07-28`, Streamable HTTP sans session, protégé par OAuth 2.1.
L'identité et les scopes du jeton sont
nécessaires mais insuffisants : chaque outil appelle aussi l'autorisation KYA sur sa ressource.

Le serveur expose un POST canonique sur `/registry/mcp` et les métadonnées RFC 9728 sur
`/.well-known/oauth-protected-resource/registry/mcp`. Le jeton doit viser exactement la ressource
canonique. Neon Auth établit l'identité ; le courtier OAuth KYA assure découverte, PKCE, consentement,
scopes et émission du jeton MCP. L'activation distante échoue fermée tant que ce courtier n'est pas
configuré.

Le parcours suit OAuth 2.1 avec PKCE : le client découvre la ressource et le serveur d'autorisation
KYA, s'enregistre, puis l'utilisateur authentifié par Neon Auth accepte ou refuse les scopes. KYA
émet ensuite un code à usage unique et un jeton opaque lié à la ressource. OpenFGA contrôle encore
chaque opération dans l'unité active ; le consentement ne crée donc jamais un droit métier.

Les secrets clients sont chiffrés au repos. Requêtes, codes et jetons sont stockés uniquement sous
forme de condensats SHA-256. Le jeton d'accès dure 15 minutes, le refresh token est rotatif et la
révocation ferme toute sa famille. DCR reste disponible pour les clients actuels, avec une migration
prévue vers les Client ID Metadata Documents recommandés par MCP `2026-07-28`.

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
