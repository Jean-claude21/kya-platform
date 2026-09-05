# Preuve US7 — Audit et administration sans contournement

**Date** : 2026-09-05

**Périmètre** : incrément de test sur l'espace `workspace:platform`

**Artefact reconstitué** : `kya:skill:document-standard`, version `1.0.0`

## Résultat démontré

La piste d'audit reconstitue le cycle d'une publication à partir d'événements append-only. Chaque
preuve contient l'acteur, son unité active, l'action, la cible, la décision, le résultat, l'heure,
l'environnement et un identifiant de corrélation. Les valeurs dont le nom évoque un secret sont
remplacées avant persistance, y compris dans les objets et listes imbriqués.

Deux mandats indépendants sont appliqués :

- `can_audit` autorise la lecture des métadonnées d'un espace précis ;
- `can_view_audit_content` autorise séparément le contenu métier protégé.

Un administrateur technique possédant uniquement le premier mandat voit les éléments nécessaires
au diagnostic, mais reçoit `protected_content: null`. Il ne peut pas élargir lui-même son accès en
ajoutant le paramètre de contenu : l'API répond `403 audit_content_permission_denied`.

## Histoire reconstituée

Tous les événements de ce scénario partagent la corrélation `01A06F70…F23`.

| Ordre | Action               | Acteur                  | Décision  | Résultat      | Cible                            |
| ----: | -------------------- | ----------------------- | --------- | ------------- | -------------------------------- |
|     1 | Candidat soumis      | Communication           | Reçue     | En validation | Skill `1.0.0`                    |
|     2 | Contrôles techniques | service de publication  | Conforme  | Réussie       | digest, manifeste, propriétaires |
|     3 | Approbation métier   | Direction Communication | Approuvée | Réussie       | demande `PR-0042`                |
|     4 | Artefact publié      | CVSI                    | Autorisée | Réussie       | version immuable `1.0.0`         |

La chronologie est renvoyée de la plus récente à la plus ancienne, puis par identifiant pour rendre
l'ordre déterministe lorsque deux événements ont le même horodatage.

## Contrôles exécutables

- `tests/domain/test_audit.py` : immutabilité profonde, absence de méthodes de modification ou de
  suppression, nettoyage récursif, portée unique et séparation du contenu ;
- `tests/integration/test_audit_api.py` : refus avant lecture du dépôt, vue métadonnées et double
  mandat pour le contenu ;
- `tests/infrastructure/test_audit_repository.py` : conversion vers `audit.event`, insertion seule,
  commit et reconstruction des deux niveaux de contenu ;
- `apps/web/src/features/audit/audit-timeline.test.tsx` : vue française, périmètre et avertissement
  explicite sur le contenu masqué.

## Protection de persistance

Le dépôt applicatif n'expose que `append` et `list_events`. En base, la migration
`20260903_0001_reliability_foundation.py` installe un trigger PostgreSQL qui rejette toute commande
`UPDATE` ou `DELETE` sur `audit.event` avec le message `audit events are append-only`.

## Limites et prochaine preuve

Cette preuve valide le comportement de l'incrément et son adapter Neon par tests automatisés. La
preuve de production devra compléter ce dossier par un export d'événements réels signés ou
horodatés, la politique de rétention et un test de restauration, sans copier de contenu sensible.
