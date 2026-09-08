# Preuves de validation — MCP Data gouverné v0.1

## Validation locale du 8 septembre 2026

- Ruff : réussi sur tout le backend ; 194 fichiers conformes au format Python.
- mypy : réussi sur 110 fichiers source.
- pytest : 422 tests réussis.
- couverture backend : 90,23 %, seuil obligatoire de 90 % atteint.
- ESLint : réussi.
- TypeScript : réussi.
- Vitest : 7 fichiers et 13 tests réussis.
- Mermaid : source validée et rendue localement en SVG et PNG ; inspection visuelle effectuée.
- `git diff --check` : aucune erreur d'espace ou de patch.

La vérification Prettier globale locale signale les fins de ligne CRLF de la machine Windows sur des
fichiers historiques non modifiés. Les fichiers Markdown introduits par cette phase sont formatés.
La CI distante sous Node 24 reste l'autorité sur la vérification globale, comme pour les phases
précédentes.

## Scénarios de sécurité couverts

- outils Data absents de `tools/list` sans portée OAuth ou sans droit OpenFGA ;
- permission recalculée lors de chaque invocation ;
- unité active imposée par le jeton ;
- appel forcé refusé et audité ;
- audit indisponible : opération fermée avant accès métier ;
- snapshot retourné sans fournisseur, conteneur, clé d'objet ni URL ;
- confirmation stricte et clé d'idempotence obligatoires pour l'ingestion ;
- recherche et lignage limités au périmètre de l'unité active ;
- métadonnées OAuth annonçant séparément catalogue, lecture Data et ingestion Data.

## Validation distante — PR 31

Les huit contrôles requis sont réussis sur le commit fonctionnel :

- politique de branche ;
- qualité backend ;
- qualité frontend et documentaire sous Node 24 ;
- modèle d'autorisation OpenFGA ;
- validation de preview ;
- validation de promotion ;
- dépendances, secrets et configuration ;
- conteneur et SBOM.
