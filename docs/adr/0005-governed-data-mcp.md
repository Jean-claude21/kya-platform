# ADR 0005 — Exposer Data Foundation par la passerelle MCP KYA unique

## Statut

Accepté le 8 septembre 2026.

## Décision

Les capacités Data sont enregistrées sur le serveur MCP existant. OAuth accorde des portées
distinctes (`data:read`, `data:ingest`) ; OpenFGA décide ensuite sur l'unité active. Les handlers
réutilisent `DataService`, ferment l'accès sans audit et retournent des projections sans secrets ni
emplacements de stockage.

## Conséquences

- Une seule connexion suffit dans Claude, ChatGPT ou un éditeur compatible.
- Le nombre d'outils visible dépend du consentement et du rôle courant.
- Les modèles ne reçoivent pas de SQL arbitraire ou de clé fournisseur.
- Le premier scraper pourra s'intégrer sans modifier les contrats de gouvernance.
- L'activation personnelle d'outils reste une extension ultérieure du profil utilisateur.
