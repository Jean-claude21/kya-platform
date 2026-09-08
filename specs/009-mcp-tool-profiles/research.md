# Recherche et décisions

## R-001 — Le profil est une réduction, jamais une autorisation

Décision : `outil effectif = actif ∩ scope ∩ OpenFGA ∩ profils − refus`. Une préférence personnelle
ne peut qu'enlever un outil en v0.1. L'autorisation de la ressource cible reste vérifiée à l'appel.

## R-002 — Une seule passerelle stateless

Décision : conserver `/registry/mcp`. MCP `2026-07-28` rend chaque requête autoportante et permet à
`tools/list` de varier selon l'autorisation de la requête, avec ordre déterministe et cache explicite.
Le profil n'est donc ni une session serveur ni un nouveau connecteur.

Sources officielles :

- [MCP 2026-07-28](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
- [Tools — spécification MCP](https://modelcontextprotocol.io/specification/draft/server/tools)

## R-003 — Cohérence par requête

Décision : le prochain `tools/list` recalcule la visibilité. Une notification
`notifications/tools/list_changed` pourra accélérer le rafraîchissement chez les clients abonnés,
mais la sécurité ne dépend pas d'un canal ouvert.

## R-004 — Sélection personnelle restrictive

Décision : en v0.1, la préférence personnelle ne connaît que `disabled`. Sa suppression signifie
`inherit`. Cela évite qu'une préférence ancienne accorde un nouvel outil après un changement de rôle.

## R-005 — Déploiement progressif

Décision : tables additives, seed idempotent, profils système, shadow mode, mesure des divergences,
puis enforcement. Le rollback réactive le filtre historique sans supprimer les données.
