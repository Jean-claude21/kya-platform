# Contrats HTTP v0.1

- `GET /api/v1/mcp/tools` : outils administrables déjà filtrés.
- `GET /api/v1/mcp/profiles` : profils visibles.
- `POST /api/v1/mcp/profiles` : création idempotente autorisée.
- `PATCH /api/v1/mcp/profiles/{key}` : modification avec `expected_revision`.
- `PUT /api/v1/mcp/profiles/{key}/tools/{tool_key}` : `enabled|disabled` explicite.
- `DELETE /api/v1/mcp/profiles/{key}/tools/{tool_key}` : retour à l'héritage.
- `POST /api/v1/mcp/profiles/{key}/assignments` : affectation temporelle.
- `DELETE /api/v1/mcp/assignments/{id}` : révocation logique.
- `GET /api/v1/mcp/me/effective-profile` : outils effectifs, révision et sources non sensibles.
- `PUT /api/v1/mcp/me/tool-preferences/{tool_key}` : désactivation personnelle.
- `DELETE /api/v1/mcp/me/tool-preferences/{tool_key}` : retour à l'héritage.

Toutes les routes exigent un Bearer Neon Auth et `X-KYA-Unit-ID`. Les mutations exigent une
autorisation fraîche, une clé d'idempotence et une révision attendue lorsqu'elles modifient un état.
