# Spécification — MCP Data gouverné v0.1

## Objectif

Permettre à Claude, ChatGPT et aux éditeurs compatibles MCP de découvrir et d'utiliser les
données KYA accessibles à l'utilisateur, depuis une connexion unique à KYA Platform. Le protocole
ne contourne ni KYA Core, ni OpenFGA, ni les services applicatifs de Data Foundation.

## Parcours prioritaires

1. Un collaborateur recherche les actifs disponibles dans son unité active.
2. Il consulte le contrat, la fraîcheur et les preuves de snapshots sans recevoir de secret ou de
   chemin de stockage.
3. Il suit le lignage exact d'un snapshot.
4. Un gestionnaire autorisé déclenche une ingestion confirmée et idempotente.
5. Un utilisateur sans droit ne découvre ni l'outil Data ni la ressource concernée.

## Exigences fonctionnelles

- **FR-001** — Le même endpoint MCP expose des modules Registry et Data sans multiplier les clés.
- **FR-002** — `tools/list` filtre les outils avec le consentement OAuth et OpenFGA.
- **FR-003** — Le jeton doit contenir une unité active ; aucune unité n'est déduite du texte libre.
- **FR-004** — Les lectures Data exigent `data:read` et `org_unit.can_view`.
- **FR-005** — Le déclenchement exige `data:ingest`, `org_unit.can_manage`, confirmation et clé
  d'idempotence.
- **FR-006** — Les outils utilisent `DataService`, jamais SQL ou Neon directement.
- **FR-007** — La recherche est bornée à 50 éléments et paginable par indication `has_more`.
- **FR-008** — Les résultats n'exposent ni référence Infisical, ni URL signée, ni conteneur, ni clé
  d'objet.
- **FR-009** — Chaque invocation Data produit une preuve append-only corrélée : acteur, unité,
  outil, cible, décision et résultat.
- **FR-010** — L'absence du service d'audit ferme l'accès avant toute opération.
- **FR-011** — Une panne ou une configuration OpenFGA absente ferme l'accès.
- **FR-012** — Les réponses utilisent des schémas Pydantic stricts et structurés.
- **FR-013** — Les Skills restent des artefacts installables et ne deviennent pas des outils
  exécutables.
- **FR-014** — Le serveur annonce les portées optionnelles sans exiger toutes les portées pour
  chaque requête HTTP.
- **FR-015** — Le protocole cible MCP `2026-07-28` et le transport Streamable HTTP sans état.

## Outils v0.1

| Outil                  | Portée OAuth  | Autorisation          | Effet                 |
| ---------------------- | ------------- | --------------------- | --------------------- |
| `discover_data_assets` | `data:read`   | `org_unit.can_view`   | recherche bornée      |
| `get_data_asset`       | `data:read`   | `org_unit.can_view`   | métadonnées           |
| `get_data_contract`    | `data:read`   | `org_unit.can_view`   | contrat et qualité    |
| `list_data_snapshots`  | `data:read`   | `org_unit.can_view`   | preuves sans stockage |
| `trace_data_lineage`   | `data:read`   | `org_unit.can_view`   | dépendances exactes   |
| `start_ingestion`      | `data:ingest` | `org_unit.can_manage` | écriture contrôlée    |

## Hors périmètre

- lecture du contenu physique d'un dataset ;
- SQL arbitraire ou accès direct à Neon ;
- scraper ou connecteur réel ;
- téléchargement par URL signée ;
- interface d'activation personnelle des outils ;
- adaptateur Frappe.

## Critères d'acceptation

- un jeton `data:read` avec accès à l'unité découvre exactement les cinq outils de lecture ;
- sans relation OpenFGA, ces outils ne figurent pas dans `tools/list` ;
- un appel forcé sans autorisation est refusé et audité ;
- les chemins internes de stockage sont absents des réponses ;
- `start_ingestion` rejette confirmation ou idempotence manquante ;
- l'ensemble du contrôle backend, de l'analyse statique et des tests reste vert.
