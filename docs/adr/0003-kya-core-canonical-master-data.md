# ADR 0003 — KYA Core comme référentiel canonique indépendant

**Statut** : accepté
**Date** : 2026-09-07

## Contexte

Les applications KYA doivent partager une organisation mouvante, les personnes, clients,
projets et sites sans reproduire les doublons et personnalisations dispersées. Frappe/ERPNext
reste utile pendant la transition, mais ne doit plus définir les identifiants ni la structure
des nouvelles applications autonomes.

## Décision

KYA Core est un domaine du monolithe modulaire FastAPI. Neon porte ses données canoniques dans
le schéma `core`. Les consommateurs utilisent ses ports applicatifs et sa Business API ; les
futurs MCP et adaptateurs Frappe utiliseront les mêmes cas d'usage.

Le modèle distingue :

- `Party`, réalité métier, de `Principal`, identité numérique ;
- personne stable, relation de travail datée et affectation à un poste datée ;
- unité stable, type extensible et relations organisationnelles historisées ;
- clients, projets et sites possédés par un périmètre organisationnel explicite.

OpenFGA décide les droits, Neon garantit les contraintes et l'outbox publie les changements dans
la même transaction. La migration crée l'unité racine `group`, mais le droit de propriétaire
reste attribué par le bootstrap sécurisé : données de référence et privilèges ne sont pas confondus.

## Options écartées

- Continuer à utiliser les DocTypes Frappe comme source unique : couplage fort et propagation des
  doublons actuels.
- Extraire immédiatement un microservice KYA Core : coût opérationnel sans besoin de charge ou de
  cycle de déploiement distinct.
- Concevoir d'abord une interface complète : elle figerait les écrans avant les contrats et les
  usages réels.

## Conséquences

- Une application peut naître sans dépendance Frappe et recevoir un adaptateur plus tard.
- Les clés et relations disposent d'une histoire auditable et d'une autorité claire.
- La v0.1 expose seulement unités, clients et projets ; contacts, personnes, postes, sites et
  relations de travail seront ouverts par tranches verticales justifiées.
- Toute modification du schéma suit une migration réversible testée sur une branche Neon isolée.

## Conditions de révision

Réexaminer l'extraction en service séparé si KYA Core acquiert un propriétaire, un niveau de
sécurité, une charge ou un cycle de publication réellement distincts du backend de la plateforme.
