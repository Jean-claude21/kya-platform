# Spécification — KYA Core v0.1

**Branche** : `feat-kya-core-foundation`

**Statut** : implémenté et vérifié
**Périmètre** : socle de données maîtresses, sans application métier ni adaptateur Frappe

## Finalité

KYA Core fournit les identifiants, relations et contrats communs sur lesquels pourront reposer les
applications autonomes, les MCP et les adaptateurs. Il représente la réalité de l'entreprise sans
figer sa structure dans une hiérarchie unique et sans confondre identité numérique, personne,
poste ou droit d'accès.

## Acteurs

- Administrateur KYA Core : gère les référentiels dans un périmètre autorisé.
- Responsable d'unité : consulte et administre les données de son unité selon son mandat.
- Application KYA : consomme la Business API avec une identité de service et un contexte délégué.
- Agent IA : consommera ultérieurement les mêmes capacités au travers d'un MCP gouverné.
- Adaptateur externe : traduit plus tard les contrats KYA vers Frappe ou un autre système.

## Scénarios prioritaires

### US1 — Représenter l'organisation mouvante

Un administrateur crée des types d'unités extensibles, des unités et des rattachements datés. Le
système refuse les auto-rattachements et les cycles hiérarchiques actifs, tout en autorisant des
relations transversales et plusieurs rattachements lorsque la politique le permet.

### US2 — Distinguer personne, accès et relation de travail

Une personne existe indépendamment de son compte. Sa relation avec KYA (collaborateur, stagiaire,
prestataire ou consultant) est datée. Son principal d'authentification peut être rattaché ou retiré
sans supprimer son histoire métier.

### US3 — Partager des clients fiables

Une unité autorisée enregistre un client représentant une personne ou une organisation. Les
contacts sont rattachés à une partie et les applications référencent l'identifiant KYA stable, pas
un nom ou une adresse électronique.

### US4 — Partager projets et sites

Un projet possède une unité responsable, un client éventuel et des sites associés. Un site existe
indépendamment d'un projet afin d'être réutilisé dans plusieurs interventions.

### US5 — Préparer toute intégration sans couplage

Une référence externe relie une entité KYA à un identifiant d'un système enregistré. Elle ne donne
aucun droit d'accès et n'autorise jamais une écriture directe dans Neon.

## Exigences fonctionnelles

- FR-001 : tous les identifiants internes sont des UUIDv7 immuables.
- FR-002 : les clés publiques sont stables, normalisées et non réutilisées.
- FR-003 : toutes les périodes métier sont semi-ouvertes `[valid_from, valid_until)` en UTC.
- FR-004 : `Party` représente une personne ou une organisation ; l'e-mail n'est jamais son identité.
- FR-005 : le statut de stagiaire est une relation de travail temporelle, pas un type permanent de personne.
- FR-006 : une affectation à un poste est historisée et ne confère aucun droit par son intitulé.
- FR-007 : les clients, projets et sites sont possédés par un périmètre organisationnel explicite.
- FR-008 : les commandes créent l'état métier et leur événement d'outbox dans la même transaction.
- FR-009 : les mutations acceptent une version attendue ou une clé d'idempotence selon le contrat.
- FR-010 : les listes sont filtrées par périmètre avant sérialisation et bornées à 100 éléments ;
  une pagination opaque sera obligatoire avant de dépasser cette limite.
- FR-011 : chaque accès exige une identité et une unité active ; OpenFGA décide l'autorisation.
- FR-012 : les erreurs publiques conservent le format Problem Details déjà adopté par la plateforme.
- FR-013 : l'unité racine `group` existe après migration afin que le premier administrateur puisse
  créer les subdivisions sans intervention technique ou écriture SQL manuelle.

## Hors périmètre

- moteur générique de formulaires ou de workflows ;
- interface d'administration complète ;
- MCP KYA Core ;
- synchronisation Frappe ;
- comptabilité, stock, paie ou CRM complet ;
- fusion automatique de doublons ;
- données géographiques ou énergétiques détaillées.

## Critères de succès

- les invariants temporels et organisationnels sont testés au niveau domaine et base ;
- les modèles persistants appartiennent au schéma PostgreSQL `core` ;
- une tranche API permet de créer et consulter unités, clients et projets dans un périmètre ;
- toute création produit un événement transactionnel sans donnée secrète ;
- les contrôles qualité existants restent verts avec une couverture globale d'au moins 90 %.

## Limites assumées de la tranche

- les listes sont bornées par `limit` ; les curseurs et filtres de recherche arrivent avec la
  première volumétrie réelle qui les exige, sans modifier les identifiants ni les agrégats ;
- les modèles personnes, relations de travail, postes, affectations, contacts et sites sont déjà
  persistables, mais leurs commandes publiques ne sont pas encore exposées ;
- aucune écriture Frappe, aucun MCP KYA Core et aucune interface métier ne sont inclus dans v0.1.
