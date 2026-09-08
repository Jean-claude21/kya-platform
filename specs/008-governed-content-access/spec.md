# Spécification — Accès gouverné au contenu v0.1

## Résultat attendu

Un collaborateur autorisé interroge depuis Claude, ChatGPT ou un autre client MCP le contenu
public collecté par KYA. Chaque passage est relié à sa source et au snapshot immuable qui l'a
produit. Le contenu externe reste explicitement non fiable : il constitue une donnée à analyser,
jamais une instruction à exécuter.

## Décision d'architecture

Le snapshot brut stocké dans Neon Object Storage reste la preuve de référence. Neon Postgres ne
contient qu'une projection reconstructible en documents et passages, optimisée pour la recherche.
La v0.1 utilise le plein texte PostgreSQL, sans appel à un modèle et sans coût d'embedding. Une
recherche hybride avec `pgvector` pourra être ajoutée plus tard, sous une politique d'embedding
versionnée et approuvée.

## Exigences

- **FR-001** — La lecture exige `data:content:read` et `org_unit.can_view`.
- **FR-002** — Seuls les actifs `public` et `active` de l'unité courante sont interrogeables.
- **FR-003** — Les actifs internes, confidentiels et restreints sont fermés par défaut.
- **FR-004** — Chaque passage possède offsets, digest de page, digest de snapshot et URI source.
- **FR-005** — Le stockage physique et ses identifiants ne sont jamais exposés au client MCP.
- **FR-006** — Le contenu externe porte toujours `untrusted_external_content`.
- **FR-007** — La projection est créée atomiquement avec la fin du run et le snapshot.
- **FR-008** — Chaque recherche et relecture est auditée avec acteur, unité et corrélation.
- **FR-009** — Recherche, taille des résultats et filtres sont bornés.
- **FR-010** — La passerelle MCP existante est réutilisée ; aucune nouvelle clé utilisateur.

## Outils

| Outil | Portée OAuth | Autorisation | Résultat |
| --- | --- | --- | --- |
| `search_data_content` | `data:content:read` | `org_unit.can_view` | passages publics classés et cités |
| `get_data_excerpt` | `data:content:read` | `org_unit.can_view` | passage exact d'une citation |

## Hors périmètre v0.1

- exposition de contenus non publics ;
- réponse générée par un LLM dans le backend ;
- embeddings et recherche vectorielle ;
- indexation des anciens snapshots ;
- autorisation fine par actif, à introduire avant les contenus internes.

## Critères d'acceptation

- une nouvelle collecte publique produit documents et passages dans la même transaction ;
- une recherche retourne seulement les contenus publics de l'unité active ;
- chaque résultat est vérifiable par URI, digests et offsets ;
- un passage peut être relu par son identifiant stable ;
- aucun emplacement Storage n'est sérialisé ;
- lint, formatage, typage et suite backend restent verts.
