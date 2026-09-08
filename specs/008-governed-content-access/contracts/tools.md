# Contrats MCP — Contenu public v0.1

## `search_data_content`

Entrées : `query` (2–300 caractères), jusqu'à 10 `asset_keys`, `limit` (1–10).

Sortie : passages, score lexical, niveau de confiance et citation complète. `has_more` indique
qu'une réponse bornée a été tronquée. L'ordre est score décroissant puis identifiant stable.

## `get_data_excerpt`

Entrée : `chunk_id` UUID.

Sortie : passage exact et même citation que la recherche. Un passage invisible ou absent retourne
`data_content_excerpt_not_found`, afin de ne pas révéler l'existence d'un contenu non autorisé.

## Citation

Une citation contient : identifiant logique, snapshot, digests snapshot/page, URL publique, date
d'observation et offsets exacts. Elle ne contient aucun fournisseur, conteneur ou chemin Storage.
