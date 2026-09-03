# Preuves — Fondation KYA Platform

**Date**: 2026-09-03

**Branche**: `feat-platform-foundation`

**Statut**: preuves partielles ; T024 reste ouvert jusqu'à validation de tous les bloqueurs

## Persistance et migrations — T014

- PostgreSQL 17.6 local éphémère ;
- `alembic upgrade head` atteint `20260903_0002` ;
- `downgrade base` puis `upgrade head` réussis ;
- schémas observés : `audit`, `reliability`, `identity` ;
- une tentative de modification de `audit.event` échoue avec
  `audit events are append-only` ;
- une tentative de rattacher une identité externe à un autre principal échoue avec
  `external identities cannot be rebound` ;
- les deux transactions de test sont annulées et ne laissent aucune ligne.

## Neon Auth JWT/JWKS — T017

- signature vérifiée par une clé issue du JWKS ;
- algorithmes asymétriques limités par une liste serveur ;
- `issuer`, `audience`, `expiration`, `issued-at` et `subject` obligatoires ;
- accès réseau JWKS déplacé hors de la boucle asynchrone ;
- rejet testé pour audience, issuer, expiration, sujet vide, claim absent et jeton vide ;
- l'identité authentifiée est immuable ; l'autorisation reste hors du JWT et relève d'OpenFGA.

## Observabilité et erreurs — T015

- chaque requête reçoit un UUID de corrélation dans le contexte, la réponse et les journaux ;
- un UUID fourni par le client est conservé seulement s'il est valide ;
- les erreurs attendues, HTTP, de validation et internes utilisent un contrat Problem Details ;
- les erreurs internes ne sont jamais renvoyées au client ;
- messages, champs imbriqués, `SecretStr`, Bearer tokens et identifiants de connexion sont masqués
  avant sérialisation JSON ;
- les journaux d'accès ne contiennent ni query string ni corps de requête.

## Transactions, idempotence et outbox — T016

- les ports `UnitOfWork`, `IdempotencyPort` et `OutboxPort` sont indépendants de SQLAlchemy ;
- le résultat et les effets externes sont enregistrés dans la transaction métier avant commit ;
- un appel identique rejoue le résultat sans rappeler le traitement ;
- une clé réutilisée avec un autre hash est rejetée ;
- une erreur métier provoque un rollback sans résultat d'idempotence ;
- le hash SHA-256 repose sur une sérialisation JSON canonique.

## Contrôles exécutés

| Contrôle                        | Résultat                             |
| ------------------------------- | ------------------------------------ |
| Ruff                            | réussi                               |
| mypy strict                     | réussi sur 20 fichiers source        |
| pytest                          | 42 tests réussis, couverture 93,35 % |
| pnpm lint/typecheck/test/format | réussi, 2 tests TypeScript           |
| Image backend Python 3.14       | construite                           |
| Santé du conteneur              | `ready`, environnement `test`        |
| Utilisateur du conteneur        | non-root, UID 10001                  |

## Limites restant à lever

- aucun projet Neon réel n'est encore provisionné ; les issuer, audience et URL JWKS restent donc
  des paramètres sans valeur réelle dans le dépôt ;
- l'environnement local exécute Node.js 22 alors que la cible CI et production est Node.js 24 ;
- l'injection de l'identité dans les routes FastAPI relève de T021 ;
- le modèle OpenFGA et sa matrice KYA relèvent de T018–T019.
