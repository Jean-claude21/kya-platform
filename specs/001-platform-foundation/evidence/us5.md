# US5 — Identités techniques et secrets

Date de contrôle : 2026-09-04

État : T053–T057 terminées ; exercice réel Infisical exécuté le 2026-09-04.

## Décisions appliquées

- Infisical reste le coffre autoritaire des valeurs ; Neon et le catalogue ne reçoivent que des
  références opaques et des métadonnées de gouvernance.
- Une identité machine utilise Universal Auth pour obtenir un jeton court. Le jeton est plafonné à
  900 secondes et encapsulé dans un type dont la représentation est masquée.
- Chaque autorisation d'usage lie exactement un bénéficiaire, une finalité, un périmètre, un
  environnement et une période fermée.
- Le demandeur ne peut pas approuver sa propre demande.
- Un secret personnel ne peut pas devenir implicitement un secret d'équipe.
- Un refus, une autorisation et une révocation produisent des événements d'audit sans valeur
  secrète.
- L'expiration et la révocation sont évaluées à chaque usage ; une décision ancienne ne suffit pas.

## Validation automatisée actuelle

```text
Backend complet : 167 tests réussis — couverture 91,45 % (seuil 90 %)
Scénarios US5 ciblés : 26 tests réussis
API de métadonnées : 3 tests d'intégration réussis
Interface web : 11 tests réussis dans l'ensemble web
TypeScript et builds client/SSR : réussis
Ruff ciblé : réussi
mypy ciblé : réussi
```

## Alignement avec Infisical

L'implémentation suit les concepts officiels : identités machines rattachées à des rôles et des
projets, Universal Auth contre `/api/v1/auth/universal-auth/login`, jetons courts avec TTL, et
séparation des secrets par projet, environnement et chemin.

Références officielles :

- <https://infisical.com/docs/documentation/platform/identities/machine-identities>
- <https://infisical.com/docs/documentation/platform/identities/universal-auth>
- <https://infisical.com/docs/documentation/platform/secrets-mgmt/project>
- <https://infisical.com/docs/documentation/platform/secrets-mgmt/concepts/secrets-rotation>

## Exercice réel T057

Projet créé par API : `KYA Platform Runtime Secrets` (`kya-platform-runtime`), avec protection
contre la suppression. L'identifiant du projet et les identifiants Universal Auth sont injectés
dans un fichier `.env` local ignoré par Git ; aucune valeur secrète n'est versionnée.

Résultats observés sans afficher de jeton ni de valeur secrète :

```text
Authentification Universal Auth       : 200
TTL émis / TTL maximal                : 900 s / 900 s
Lecture de la sonde en staging        : 200
Écriture après passage au rôle Viewer : 403
Lecture de la sonde en production     : 404 (aucune valeur créée)
Lecture après révocation du jeton     : 401
Nouvelle session après révocation     : 200, TTL 900 s
Résolveur Python réel                 : lecture réussie, représentation masquée
```

L'identité `kya-platform-preview` a été ramenée à `No Access` dans l'organisation, `Viewer` dans
le projet, et protégée contre la suppression. Elle ne peut plus administrer l'organisation ni
écrire des secrets.

La formule Infisical Free ne permet pas un rôle personnalisé limité à un seul environnement. En
conséquence, aucun secret de production ne doit être placé dans ce projet. La production utilisera
un projet et une identité machine distincts ; cette séparation est une condition de mise en
production. Le résolveur de la preview reçoit par configuration un environnement fixe `staging`
et n'expose aucune API permettant à un appelant de le remplacer.

Le Client Secret d'amorçage reste hors d'Infisical et doit être injecté au runtime par
Dokploy/Coolify, jamais commité. Sa rotation est indépendante des jetons d'accès de 900 secondes.
