# US5 — Identités techniques et secrets

Date de contrôle : 2026-09-04

État : socle de sécurité T053–T055 terminé ; administration API/UI T056 et exercice T057 encore à
finaliser.

## Décisions appliquées

- Infisical reste le coffre autoritaire des valeurs ; Neon et le catalogue ne reçoivent que des
  références opaques et des métadonnées de gouvernance.
- Une identité machine utilise Universal Auth pour obtenir un jeton court. Le jeton est plafonné à
  7 200 secondes par défaut et encapsulé dans un type dont la représentation est masquée.
- Chaque autorisation d'usage lie exactement un bénéficiaire, une finalité, un périmètre, un
  environnement et une période fermée.
- Le demandeur ne peut pas approuver sa propre demande.
- Un secret personnel ne peut pas devenir implicitement un secret d'équipe.
- Un refus, une autorisation et une révocation produisent des événements d'audit sans valeur
  secrète.
- L'expiration et la révocation sont évaluées à chaque usage ; une décision ancienne ne suffit pas.

## Validation automatisée actuelle

```text
Backend complet : 156 tests réussis — couverture 91,83 % (seuil 90 %)
Scénarios US5 ciblés : 9 tests réussis
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

## Conditions restantes

T056 doit exposer uniquement les métadonnées autorisées dans l'API et l'interface. T057 exigera un
exercice automatisé complet : accès preview accepté, tentative production refusée, expiration
refusée, révocation d'urgence refusée, et vérification qu'aucune valeur n'apparaît dans les logs ou
réponses.

Aucun identifiant Infisical réel n'est requis avant le branchement d'un environnement. Le moment
venu, le Client ID et le secret d'amorçage devront être injectés au runtime, jamais commités.
