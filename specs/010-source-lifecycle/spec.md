# Spécification — Cycle de vie autonome des sources v0.1

**Branche** : `feat-source-lifecycle`
**Date** : 2026-09-08
**Statut** : prêt pour implémentation

## Scénarios utilisateurs

### US1 — Configurer un flux complet sans SQL (P1)

Un administrateur Data autorisé enregistre une source, son actif brut, son contrat et son pipeline
par une commande unique. La commande est atomique et rejouable : elle ne laisse aucun objet partiel
et ne crée aucun doublon.

**Test indépendant** : configurer une source web dans une unité vide crée les quatre objets actifs ;
rejouer la même clé d'idempotence retourne le même flux.

### US2 — Piloter le cycle de vie (P1)

Un administrateur met en pause ou réactive un flux complet. Une source ou un pipeline en pause ne
peut pas démarrer une nouvelle ingestion. Les snapshots existants restent consultables.

**Test indépendant** : mettre un flux actif en pause bloque le démarrage, puis sa réactivation le
rend à nouveau exécutable sans perdre son historique.

### US3 — Planifier des ingestions durables (P2)

Un administrateur définit une cadence simple et un fuseau horaire. Un ordonnanceur serveur crée les
runs échus avec idempotence, même après un redémarrage, sans dépendre de Claude ou ChatGPT.

**Test indépendant** : une échéance active produit exactement un run et avance sa prochaine date ;
deux passages concurrents ne produisent pas de doublon.

### US4 — Comprendre la santé d'un flux (P2)

Un utilisateur autorisé consulte l'état du flux, la dernière exécution, la prochaine échéance et la
qualité du dernier snapshot sans recevoir de secret ni d'emplacement de stockage.

## Cas limites

- Le connecteur est absent, non publié ou d'un autre type : aucune ressource n'est créée.
- Une clé stable existe avec une définition différente : conflit explicite, aucune mise à jour implicite.
- Une pause intervient pendant un run : le run courant se termine, aucun nouveau run ne démarre.
- Une échéance est manquée : un seul run de rattrapage est créé, sans rafale historique.
- Neon ou l'autorisation est indisponible : refus fermé et aucune mutation partielle.
- Les références Infisical restent opaques ; aucune valeur secrète n'entre dans Neon ou les réponses.

## Exigences fonctionnelles

- **FR-001** — Créer atomiquement source, actif, contrat et pipeline par une commande idempotente.
- **FR-002** — Résoudre le connecteur par clé et version publiée, jamais par UUID fourni aveuglément.
- **FR-003** — Refuser les collisions de clés ou de définitions sans modifier l'existant.
- **FR-004** — Appliquer activation et pause à l'ensemble du flux avec transition déterministe.
- **FR-005** — Conserver une révision optimiste pour toute mutation du flux ou de sa planification.
- **FR-006** — Supporter une cadence bornée en minutes et une prochaine échéance explicite en UTC.
- **FR-007** — Réserver l'ordonnancement aux pipelines actifs dont la source et l'actif sont actifs.
- **FR-008** — Garantir au plus un run planifié par échéance logique.
- **FR-009** — Exposer une vue de santé sans secret, URL signée ni chemin Storage.
- **FR-010** — Produire événements d'outbox et audit corrélables pour chaque mutation.
- **FR-011** — Réutiliser le moteur d'ingestion existant ; l'ordonnanceur ne collecte aucune donnée.
- **FR-012** — Autoriser et revalider chaque commande côté serveur dans l'unité active.

## Entités

- **SourceFlow** : agrégat opérationnel reliant source, actif, contrat et pipeline.
- **IngestionSchedule** : cadence, prochaine échéance, état, révision et dernière échéance réclamée.
- **FlowHealth** : projection de lecture calculée à partir du flux, du planning et du dernier run.

## Critères de réussite

- **SC-001** — Une configuration complète nécessite une seule commande et zéro SQL manuel.
- **SC-002** — Un échec à n'importe quelle validation laisse zéro nouvelle ligne fonctionnelle.
- **SC-003** — Cent tentatives concurrentes pour une même échéance créent au plus un run.
- **SC-004** — La pause est visible à la requête suivante et bloque immédiatement tout nouveau run.
- **SC-005** — La vue de santé répond en moins de 300 ms au périmètre pilote.

## Hors périmètre v0.1

- éditeur Cron arbitraire ;
- orchestration de graphes multi-pipelines ;
- suppression physique des données ou snapshots ;
- exécution des analyses IA dans l'ordonnanceur ;
- interface graphique avancée de monitoring.

## Hypothèses

- La cadence minimale est de quinze minutes.
- Les analyses programmées restent dans Claude/ChatGPT ; seule l'acquisition est planifiée ici.
- Les connecteurs sont des artefacts publiés du catalogue KYA-Platform.
