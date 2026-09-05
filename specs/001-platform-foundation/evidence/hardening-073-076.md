# Preuves T073–T076 — Durcissement de la fondation

Date de contrôle : 2026-09-05

## T073 — Notifications

- préférences explicites par destinataire, sujet et canal ;
- canal désactivé supprimé avant livraison ;
- réservation atomique empêchant deux livraisons concurrentes ;
- libération de la réservation lors d'un échec afin de permettre le retry de l'outbox ;
- templates identifiés et variables bornées ; noms ressemblant à des secrets rejetés ;
- adaptateur `dispatch` compatible avec le runner d'outbox existant.

## T074 — Déprovisionnement

Le mapping SQL exclut toute identité portant `disabled_at`. API et MCP utilisent désormais ce même
mapping. Le MCP expose l'identifiant interne KYA, jamais le sujet externe Neon. Un test rejoue le
même JWT avant et après désactivation : accepté avant, refusé après.

## T075 — Intégrité des artefacts

- signature Ed25519 sur un message versionné et séparé par domaine ;
- vérification du digest, de la clé de confiance et de la signature ;
- clé inconnue ou signature modifiée refusée ;
- compromission d'une clé révoquant les versions associées ;
- représentation du signataire sans matière privée.

## T076 — Charge bornée

Le banc local exécute : 500 décisions d'autorisation, 250 recherches catalogue, 200 requêtes API
concurrentes et 2 000 validations de demandes MCP. Les seuils sont alignés sur le plan : décision
d'autorisation p95 sous 100 ms et API/catalogue p95 sous 500 ms.

## Résultat global

```text
Backend : 210 tests réussis
Couverture : 90,76 % (seuil 90 %)
Ruff : réussi après correction mécanique d'un ordre d'import
Mypy : réussi sur 75 fichiers source
```
