<!--
Sync Impact Report
- Version change: template non ratifié → 1.0.0
- Modified principles:
  - Placeholders du modèle → I. Spécification et traçabilité avant implémentation
  - Placeholders du modèle → II. Modularité, contrats et sources autoritaires
  - Placeholders du modèle → III. Sécurité contextuelle et moindre privilège
  - Placeholders du modèle → IV. IA pour le raisonnement, logiciel pour l'exécution
  - Placeholders du modèle → V. Qualité vérifiable, observabilité et réversibilité
- Added sections:
  - Contraintes d'architecture et de sécurité
  - Cycle de développement et portes de qualité
- Removed sections: aucune
- Follow-up TODOs: aucun
-->
# Constitution de KYA Platform

## Core Principles

### I. Spécification et traçabilité avant implémentation

Toute fonctionnalité, intégration ou modification significative DOIT suivre le cycle Spec Kit :
constitution, spécification du besoin, clarification, plan, tâches, analyse de cohérence,
implémentation et convergence. La spécification décrit le besoin, les acteurs, les règles,
les critères d'acceptation et les cas limites avant de choisir les détails techniques.

Chaque décision structurante DOIT être consignée dans un ADR avec le contexte, les options
étudiées, la décision, ses conséquences et ses conditions de révision. Les exigences, tâches,
commits, tests, versions et déploiements DOIVENT rester reliés afin qu'une décision ou une
fonctionnalité puisse être auditée de bout en bout. Une urgence peut raccourcir le processus,
mais ne peut supprimer ni la traçabilité ni la validation a posteriori.

### II. Modularité, contrats et sources autoritaires

KYA Platform DOIT être conçue comme un monolithe modulaire pouvant être déployé rapidement,
mais dont les domaines restent isolés par des contrats explicites. Un module ne DOIT pas lire
ou modifier directement les données privées d'un autre module. Les interfaces publiques,
schémas, événements et manifestes sont versionnés, validés et testés par contrat.

Chaque type de donnée métier DOIT posséder une source autoritaire déclarée. Neon est la source
autoritaire des données propres au Hub : catalogue, versions, espaces, politiques,
installations, publications et audits. Frappe/ERPNext et les autres applications sont des
systèmes enregistrés ; ils restent autoritaires pour les domaines métier qui leur sont
explicitement attribués. Le Hub référence et orchestre leurs capacités sans dupliquer leurs
données sans justification documentée.

Le Hub est un plan de contrôle : il découvre, gouverne, distribue et audite. Il ne DOIT pas
devenir l'exécuteur universel de toutes les capacités métier. Un module n'est extrait dans un
dépôt ou service séparé que si son cycle de publication, sa sécurité, son propriétaire, son
déploiement ou sa charge le justifie.

### III. Sécurité contextuelle et moindre privilège

Toute autorisation DOIT être évaluée côté serveur à partir de l'identité, de l'action, de la
ressource, du rôle, du périmètre organisationnel, de l'espace, de l'environnement, de la
relation avec la ressource, de la période de validité et des conditions applicables. Les rôles
globaux implicites et les contrôles uniquement réalisés dans l'interface sont interdits.

Les permissions sont refusées par défaut. Les délégations sont explicites, limitées dans le
temps lorsque pertinent, révocables et auditées. Les identités humaines, identités de service,
sessions et responsabilités sont distinctes. Les opérations sensibles exigent une validation
renforcée et, si le risque le justifie, une séparation entre demandeur et approbateur.

Aucun secret en clair ne DOIT être stocké dans Git, les manifestes, les journaux ou les tables
fonctionnelles de Neon. Le système conserve des références vers un gestionnaire de secrets et
applique séparation des environnements, rotation, expiration, révocation, journalisation sans
valeur secrète et procédure d'accès d'urgence contrôlée. Une clé personnelle ne DOIT jamais
devenir silencieusement une clé d'équipe ou de production.

### IV. IA pour le raisonnement, logiciel pour l'exécution

L'IA sert à explorer, expliquer, proposer, prototyper et orchestrer. Les validations, calculs
critiques, règles d'autorisation, transitions d'état et écritures métier DOIVENT être exécutés
par du logiciel déterministe, testable et observable.

Un Skill encode une méthode, un standard ou un contexte ; il n'est pas un outil exécutable.
Un serveur MCP expose des capacités exécutables avec des contrats, autorisations et journaux.
Le Hub peut recommander une combinaison de Skills et d'outils MCP, mais aucun agent ne peut
télécharger ou exécuter arbitrairement du code non approuvé. Les actions à impact externe ou
irréversible exigent une confirmation adaptée au risque et une preuve d'autorisation fraîche.

Les prototypes métiers sont développés en environnement isolé avec données synthétiques ou
masquées. Ils ne rejoignent le catalogue approuvé et les systèmes de production qu'après
revue, tests, attribution d'un propriétaire et industrialisation selon les portes de qualité.

### V. Qualité vérifiable, observabilité et réversibilité

Une fonctionnalité n'est terminée que si ses critères d'acceptation sont démontrés par des
tests proportionnés au risque. Les règles de domaine, contrats, autorisations, migrations et
intégrations critiques exigent des tests automatisés. Toute correction de défaut ajoute un
test de non-régression lorsque cela est techniquement possible.

Les services produisent des journaux structurés, métriques, traces ou événements d'audit
permettant de répondre à qui a fait quoi, sur quelle ressource, dans quel périmètre, quand et
avec quel résultat, sans exposer de donnée secrète. Les migrations, publications,
installations et déploiements DOIVENT posséder une stratégie documentée de reprise ou de retour
arrière. La simplicité et la réutilisation sont privilégiées, mais jamais au détriment de la
sécurité, de la lisibilité, de l'accessibilité ou de la preuve de fonctionnement.

## Contraintes d'architecture et de sécurité

- Le dépôt initial est un workspace unique avec des limites d'import automatisables entre
  domaines, des contrats publics et aucune dépendance circulaire.
- L'interface TanStack, la Business API, le Registry MCP et les workers partagent les services
  de domaine ; ils ne réimplémentent pas les mêmes règles.
- Les API consommables hors de l'interface sont explicites, versionnées et indépendantes des
  mécanismes RPC propres au framework Web.
- Le modèle organisationnel représente Groupe, pays, entités, agences, directions,
  départements, équipes, projets, communautés, espaces temporaires, postes et affectations
  historisées sans coder une hiérarchie rigide.
- Les artefacts enregistrés incluent au minimum systèmes, applications, API, Data Products,
  serveurs et outils MCP, Skills, templates, Design Systems, politiques et versions.
- Les environnements local, preview, test et production sont isolés. Une Pull Request reçoit
  une preview applicative et, lorsque nécessaire, une branche de données dédiée.
- Les migrations de schéma sont immuables après publication, revues et exécutées par le
  pipeline. Les changements manuels de schéma en production sont interdits.
- Les dépendances et artefacts de livraison sont verrouillés, analysés, identifiables et
  promus entre environnements sans reconstruction différente de l'artefact validé.
- Les données personnelles, sensibles ou réglementées sont classifiées ; leur collecte,
  exposition, rétention, export et suppression suivent des politiques vérifiables.
- Les exigences d'accessibilité, d'internationalisation, de fuseau horaire et de faible bande
  passante sont prises en compte dans les critères d'acceptation des interfaces concernées.

## Cycle de développement et portes de qualité

1. Une recherche ciblée examine les spécifications, documentations officielles, projets de
   référence maintenus et contraintes KYA avant toute décision technologique structurante.
2. Spec Kit produit et maintient la spécification, les clarifications, le plan et les tâches.
3. Un contrôle de constitution vérifie explicitement architecture, autorisation, secrets,
   données, observabilité, réversibilité et documentation.
4. L'implémentation procède par petites tranches verticales démontrables, avec tests écrits au
   plus tard avec le comportement concerné et avant intégration.
5. Chaque Pull Request passe formatage, analyse statique, tests unitaires, tests de contrat,
   contrôles de sécurité et tests d'intégration pertinents avant preview.
6. Les changements d'autorisation, de secrets, de migrations, de dépendances sensibles et de
   pipeline exigent une revue humaine qualifiée.
7. La fusion déclenche l'environnement de test. La production reçoit par promotion un artefact
   immuable validé et requiert une approbation explicite tant que l'automatisation n'a pas fait
   l'objet d'une décision de gouvernance contraire.
8. Toute version publiée possède notes de version, compatibilité, propriétaire, procédure de
   retour arrière et éléments d'audit. La documentation fait partie de la livraison.

## Governance

Cette constitution prévaut sur les conventions locales, prompts, habitudes d'équipe et sorties
d'agents IA. Toute exception DOIT être documentée, limitée, approuvée par le responsable
technique compétent et assortie d'une échéance ou d'une condition de suppression.

Une modification constitutionnelle exige une proposition motivée, une analyse d'impact sur les
spécifications et systèmes existants, une validation du CVSI et, pour un changement touchant la
gouvernance Groupe, la sécurité ou les responsabilités des Directions, l'approbation de
l'autorité désignée par KYA. Les versions suivent SemVer : MAJOR pour une rupture de principe,
MINOR pour un principe ou une obligation substantielle ajoutée, PATCH pour une clarification
sans changement d'exigence.

Chaque plan Spec Kit et chaque Pull Request DOIT déclarer sa conformité à la constitution ou
l'exception approuvée. Un audit de conformité est réalisé avant toute première mise en
production d'un domaine et périodiquement ensuite. Les dérogations expirées bloquent une
publication. La constitution est réexaminée au minimum à chaque changement d'architecture
majeur ou de modèle de gouvernance.

**Version**: 1.0.0 | **Ratified**: 2026-09-03 | **Last Amended**: 2026-09-03
