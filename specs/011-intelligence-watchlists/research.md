# Recherche ciblée — Veilles KYA Intelligence

## Décisions

### Détection déterministe, raisonnement externe

La plateforme évalue une requête bornée sur des fragments déjà gouvernés et enregistre les preuves
correspondantes. Elle ne génère pas elle-même une conclusion. Cela respecte le principe KYA
« IA pour le raisonnement, logiciel pour l'exécution » et évite de dupliquer les abonnements Claude
ou ChatGPT des collaborateurs.

### Outils MCP fins et profilables

La spécification MCP 2026-07-28 distingue ressources, prompts et outils, demande le consentement de
l'utilisateur et recommande des contrôles d'accès robustes. Les cinq capacités Intelligence sont
donc séparées, filtrées par profil et par scopes existants `data:read` / `data:ingest`. Les trois
mutations exigent confirmation et idempotence.

Source primaire : https://modelcontextprotocol.io/specification/2026-07-28

### Preuve immuable, état de traitement mutable

Le signal copie l'extrait et ses empreintes au moment de la détection pour préserver la preuve. Seul
l'état opérationnel `open/acknowledged` évolue avec une révision optimiste. L'acquittement ne modifie
jamais la citation, l'URI ou les empreintes.

### Pas de recherche vectorielle en v0.1

Le PostgreSQL full-text existant est explicable, économique et déjà alimenté. Une recherche hybride
ne sera introduite qu'après un corpus et des mesures réelles de rappel/précision.

## Alternatives écartées

- **Chat intégré à KYA Intelligence** : coût et interface dupliqués, liberté de modèle réduite.
- **Stocker tous les résultats générés par IA** : mélange preuve/opinion et provenance ambiguë.
- **Un outil MCP unique polyvalent** : descriptions plus floues, autorisations moins fines et charge
  d'outils plus difficile à maîtriser.
