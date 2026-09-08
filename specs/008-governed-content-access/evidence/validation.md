# Validation

Date : 2026-09-08

- lint Ruff : succès ;
- formatage Ruff : succès ;
- typage mypy : succès, 123 fichiers source ;
- tests backend : 449 tests réussis, couverture à 90,02 % ;
- diagramme Mermaid : syntaxe validée et exports SVG/PNG générés avec Mermaid CLI 11.17.0 ;
- PR fonctionnelle : [#37](https://github.com/Jean-claude21/kya-platform/pull/37), contrôles GitHub réussis ;
- correctif d'ordre transactionnel parent/enfants :
  [#38](https://github.com/Jean-claude21/kya-platform/pull/38), contrôles GitHub réussis ;
- migration : révision `20260908_0013` appliquée uniquement à la base active de `dev` ;
- déploiement : backend et worker `dev` sains au commit `e1dee501` ;
- pilote réel : collecte institutionnelle terminée avec 1 snapshot, 25 documents et
  32 fragments, sans écriture partielle lors de la tentative initiale en échec ;
- recherche réelle : la requête `solaire` retourne 16 fragments gouvernés pour l'actif
  public `kya-institutional-web-capture` ;
- citation vérifiée : identifiants de fragment et snapshot, URI source, empreintes snapshot
  et page, offsets exacts et niveau de confiance sont présents, sans localisation Storage ;
- découverte OAuth : la portée `data:content:read` est publiée par la ressource MCP déployée.

Les environnements `staging` et `production` n'ont pas été modifiés.
