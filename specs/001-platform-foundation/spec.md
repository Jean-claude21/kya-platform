# Feature Specification: Fondation de KYA Platform

**Feature Branch**: `feat-platform-foundation`

**Created**: 2026-09-03

**Status**: Draft

**Input**: Mettre en place une plateforme interne permettant à KYA de gouverner, partager,
publier, installer et auditer ses systèmes, applications, API, données, MCP, Skills, modèles
et standards dans des espaces organisationnels finement contrôlés.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Accéder à un espace selon ses responsabilités (Priority: P1)

Un collaborateur accède aux espaces correspondant à ses affectations et n'y voit que les
ressources et actions autorisées pour son rôle, son équipe, sa Direction, son projet, son pays
et la période concernée.

**Why this priority**: La confidentialité et le partage maîtrisé conditionnent toutes les autres
fonctions de la plateforme.

**Independent Test**: Créer plusieurs personnes ayant des affectations différentes, leur faire
consulter le même ensemble d'espaces et vérifier que chacune ne voit et ne réalise que ce qui lui
est explicitement permis.

**Acceptance Scenarios**:

1. **Given** une personne membre d'une équipe, **When** elle ouvre l'espace de cette équipe,
   **Then** elle voit uniquement les ressources permises par son rôle dans cet espace.
2. **Given** une personne sans affectation ni partage applicable, **When** elle tente d'accéder
   directement à une ressource, **Then** l'accès est refusé et la tentative est auditée.
3. **Given** une affectation arrivée à expiration, **When** la personne tente une action autrefois
   autorisée, **Then** l'action est refusée sans délai.
4. **Given** une personne travaillant dans plusieurs périmètres, **When** elle change d'espace,
   **Then** ses droits sont recalculés selon le contexte actif sans mélanger les périmètres.

---

### User Story 2 - Publier et partager un artefact KYA (Priority: P1)

Un métier ou le CVSI prépare un Skill, un MCP, une application, une API, un modèle ou un standard,
le soumet dans son espace, obtient les validations requises et le publie vers les publics autorisés.

**Why this priority**: Cette chaîne transforme les productions dispersées en patrimoine KYA
identifiable, réutilisable et gouverné.

**Independent Test**: Publier un artefact depuis un espace d'équipe jusqu'au catalogue Groupe,
avec une validation et une version, puis vérifier sa découverte par un utilisateur autorisé.

**Acceptance Scenarios**:

1. **Given** un brouillon complet appartenant à une équipe, **When** son propriétaire le soumet,
   **Then** les validateurs applicables reçoivent une demande contenant les preuves nécessaires.
2. **Given** une demande approuvée, **When** la publication est effectuée, **Then** une version
   immuable devient visible uniquement dans les périmètres choisis.
3. **Given** une demande rejetée, **When** l'auteur la consulte, **Then** il voit les motifs et peut
   préparer une nouvelle révision sans altérer l'historique.

---

### User Story 3 - Découvrir, installer et mettre à jour (Priority: P1)

Un collaborateur recherche une capacité adaptée à son besoin, comprend son propriétaire, son
niveau de confiance, ses dépendances et ses droits, puis demande son installation ou sa mise à jour
depuis l'interface ou un environnement IA autorisé.

**Why this priority**: La valeur du catalogue dépend de la capacité des personnes à utiliser les
éléments approuvés sans intervention manuelle systématique du CVSI.

**Independent Test**: Rechercher un Skill publié, demander son installation, détecter une nouvelle
version, l'appliquer puis revenir à la version précédente avec une piste d'audit complète.

**Acceptance Scenarios**:

1. **Given** plusieurs artefacts similaires, **When** une personne décrit son besoin, **Then** elle
   obtient des résultats filtrés par droits, compatibilité, statut et contexte.
2. **Given** une installation autorisée, **When** la personne la confirme, **Then** elle peut suivre
   son état et reçoit un résultat vérifiable.
3. **Given** une nouvelle version compatible, **When** la vérification quotidienne s'exécute,
   **Then** la mise à jour est proposée selon la politique applicable.
4. **Given** une mise à jour défaillante, **When** un retour arrière est demandé, **Then** la dernière
   version saine est restaurée et l'incident est audité.

---

### User Story 4 - Enregistrer les systèmes et leurs autorités de données (Priority: P2)

Un architecte référence Frappe/ERPNext ou une autre application, décrit ses capacités, ses données,
ses responsables et les entités pour lesquelles ce système fait foi.

**Why this priority**: La plateforme ne peut orchestrer correctement les capacités du Groupe sans
savoir où se trouvent les données et quel système en est responsable.

**Independent Test**: Enregistrer Frappe, déclarer une entité dont il est la source autoritaire et
vérifier que le catalogue renvoie le bon système et les moyens d'accès autorisés.

**Acceptance Scenarios**:

1. **Given** un système enregistré, **When** une capacité ou une entité est consultée, **Then** son
   propriétaire, son autorité, sa sensibilité et ses interfaces approuvées sont explicites.
2. **Given** deux systèmes revendiquant la même autorité, **When** la déclaration est soumise,
   **Then** la publication est bloquée jusqu'à résolution du conflit.

---

### User Story 5 - Gérer identités techniques et secrets (Priority: P2)

Un responsable autorisé attribue à une personne, une équipe, une application ou un MCP l'usage
limité d'une identité technique ou d'un secret sans en exposer la valeur aux personnes non habilitées.

**Why this priority**: Les intégrations et déploiements ne peuvent être sûrs sans propriété,
portée, rotation et révocation explicites des accès techniques.

**Independent Test**: Accorder temporairement l'usage d'un secret de test à un service, vérifier
qu'il ne fonctionne ni en production ni après expiration, puis le révoquer et auditer le cycle.

**Acceptance Scenarios**:

1. **Given** un secret associé à un environnement et un espace, **When** un service autorisé le
   demande pour l'usage prévu, **Then** il reçoit un accès limité sans exposition dans les journaux.
2. **Given** une identité personnelle, **When** un utilisateur tente de la partager comme identité
   d'équipe, **Then** l'opération est refusée.
3. **Given** un secret expiré ou révoqué, **When** un service tente de l'utiliser, **Then** l'accès
   échoue et une alerte exploitable est produite.

---

### User Story 6 - Promouvoir une version entre environnements (Priority: P2)

Une équipe transforme une modification isolée en version testée, vérifiable et promue vers les
environnements de validation puis de production, avec approbations et retour arrière.

**Why this priority**: L'autonomie de développement doit rester compatible avec la stabilité et la
sécurité du système d'information.

**Independent Test**: Faire passer une version depuis une modification proposée jusqu'à la
production, vérifier l'isolation des données et secrets, puis restaurer la version précédente.

**Acceptance Scenarios**:

1. **Given** une modification proposée, **When** elle est soumise à revue, **Then** un environnement
   isolé est disponible avec des accès non productifs.
2. **Given** des contrôles en échec, **When** une promotion est demandée, **Then** elle est bloquée
   avec des résultats compréhensibles.
3. **Given** une version validée, **When** l'approbateur autorise la production, **Then** la version
   exacte déjà contrôlée est promue sans substitution silencieuse.

---

### User Story 7 - Auditer et administrer sans contourner les règles (Priority: P3)

Un auditeur ou administrateur consulte l'historique des décisions, partages, accès sensibles,
publications, installations et déploiements selon son propre périmètre d'autorisation.

**Why this priority**: La gouvernance doit être démontrable sans créer de rôle omnipotent invisible.

**Independent Test**: Reconstituer le cycle complet d'un artefact et prouver l'identité, le contexte,
la décision et le résultat de chaque opération sensible.

**Acceptance Scenarios**:

1. **Given** une opération sensible terminée, **When** un auditeur habilité la recherche, **Then** il
   retrouve l'auteur, le contexte, la cible, la décision et le résultat.
2. **Given** un administrateur technique sans mandat métier, **When** il tente de consulter un contenu
   confidentiel, **Then** le contenu reste inaccessible même si les métadonnées techniques nécessaires
   à l'exploitation lui sont visibles.

### Edge Cases

- Une unité organisationnelle est déplacée, fusionnée, renommée ou fermée alors que des droits et
  artefacts actifs y sont rattachés.
- Une personne change de poste, cumule plusieurs affectations ou quitte l'entreprise.
- Une équipe partage une ressource avec un projet transversal dont les membres viennent de plusieurs
  Directions ou pays.
- Un stagiaire contribue à un brouillon, puis son accès expire avant la publication.
- Le propriétaire unique d'un artefact ou d'une identité technique devient indisponible.
- Une dépendance est retirée, compromise ou devient incompatible avec une version installée.
- Une mise à jour est découverte alors que l'installation locale a été modifiée.
- Un fournisseur de déploiement est indisponible pendant une promotion ou un retour arrière.
- Un environnement temporaire est supprimé alors qu'il possède encore des ressources externes.
- Un conflit apparaît entre une permission héritée et une interdiction explicite.
- Une demande tente d'énumérer des ressources auxquelles son auteur n'a pas accès.
- Une clé fuit, est révoquée en urgence ou doit être remplacée sans interruption prolongée.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Le système DOIT représenter une organisation évolutive composée de types d'unités
  configurables et de relations hiérarchiques ou transversales historisées.
- **FR-002**: Le système DOIT représenter séparément personnes, comptes, identités de service,
  postes, rôles, équipes et affectations.
- **FR-003**: Une personne DOIT pouvoir cumuler plusieurs affectations ayant des périmètres, rôles,
  dates et responsables différents.
- **FR-004**: Le système DOIT proposer des espaces personnels, d'équipe, de Direction, de projet,
  de pays, Groupe, temporaires et restreints, sans imposer qu'un espace corresponde à une seule unité.
- **FR-005**: Toute décision d'accès DOIT considérer l'identité, l'action, la ressource, le rôle, le
  périmètre, l'espace, l'environnement, la relation, la validité temporelle et les interdictions.
- **FR-006**: Toute action non explicitement autorisée DOIT être refusée.
- **FR-007**: Les autorisations DOIVENT pouvoir être héritées, déléguées, limitées dans le temps,
  interdites explicitement et révoquées, avec des règles de priorité non ambiguës.
- **FR-008**: Le système DOIT permettre de simuler et expliquer une décision d'autorisation sans
  révéler des ressources ou politiques confidentielles.
- **FR-009**: Les actions à risque DOIVENT pouvoir exiger plusieurs responsabilités distinctes,
  notamment demande, revue et approbation.
- **FR-010**: Le système DOIT enregistrer systèmes, applications, API, produits de données, serveurs
  MCP, outils MCP, Skills, modèles, Design Systems, politiques et templates sous un modèle commun.
- **FR-011**: Chaque artefact DOIT avoir un identifiant stable, un propriétaire métier, un
  responsable technique, un espace, une visibilité, une sensibilité et un état de cycle de vie.
- **FR-012**: Chaque version publiée DOIT être immuable, identifiable, documentée et reliée à ses
  dépendances, compatibilités, validations et éléments de provenance.
- **FR-013**: Le système DOIT gérer les états brouillon, prototype, candidat, en validation,
  approuvé, publié, suspendu, déprécié et retiré avec des transitions autorisées.
- **FR-014**: Le système DOIT empêcher la publication lorsqu'une validation, un propriétaire, une
  compatibilité ou une preuve obligatoire manque.
- **FR-015**: Le système DOIT permettre le partage ciblé avec une personne, une équipe, une unité,
  un projet, un pays, un rôle, plusieurs périmètres ou tout le Groupe.
- **FR-016**: Les résultats de recherche et recommandations DOIVENT être filtrés avant affichage
  selon les droits et le contexte du demandeur.
- **FR-017**: Un utilisateur autorisé DOIT pouvoir découvrir, demander, installer, mettre à jour,
  désactiver et retirer un artefact depuis une interface humaine ou un client automatisé approuvé.
- **FR-018**: Le système DOIT distinguer une méthode ou instruction destinée à un agent d'une
  capacité exécutable et ne jamais présenter la première comme un programme directement exécutable.
- **FR-019**: Toute installation DOIT vérifier l'autorisation, l'intégrité, la provenance, la
  compatibilité, les dépendances et la politique de l'environnement cible.
- **FR-020**: Le système DOIT vérifier au moins quotidiennement les versions disponibles et appliquer
  une politique distincte aux correctifs de sécurité, correctifs, évolutions et ruptures.
- **FR-021**: Une mise à jour DOIT pouvoir être testée, approuvée, suivie et annulée sans perdre
  l'historique de l'installation précédente.
- **FR-022**: Chaque système enregistré DOIT déclarer ses capacités, responsables, environnements,
  interfaces approuvées et niveau de disponibilité connu.
- **FR-023**: Chaque catégorie de donnée partagée DOIT avoir une source autoritaire explicite ; les
  conflits d'autorité DOIVENT bloquer la publication jusqu'à résolution.
- **FR-024**: Le système DOIT référencer Frappe/ERPNext comme un système externe et permettre de
  déclarer les domaines métier pour lesquels il fait foi sans copier leur contenu par défaut.
- **FR-025**: Le système DOIT distinguer secrets personnels, d'équipe, de service, d'application et
  d'environnement, ainsi que leurs propriétaires, usages, bénéficiaires et cycles de vie.
- **FR-026**: La valeur d'un secret NE DOIT PAS apparaître dans le catalogue, les journaux, les
  exports, les notifications ou les historiques fonctionnels.
- **FR-027**: Les usages de secrets DOIVENT être limités par finalité, identité, périmètre,
  environnement et durée, avec rotation, révocation et accès d'urgence contrôlé.
- **FR-028**: Les environnements de développement isolé, revue, validation et production DOIVENT
  utiliser des données et secrets séparés selon leur niveau de risque.
- **FR-029**: Chaque modification proposée DOIT disposer d'un environnement de revue isolé lorsque
  le changement peut affecter une application, une donnée, une intégration ou un déploiement.
- **FR-030**: Une version NE DOIT PAS être promue si un contrôle obligatoire échoue ou si une
  approbation requise manque.
- **FR-031**: La production DOIT recevoir le même contenu immuable que celui qui a été validé, et
  chaque promotion DOIT disposer d'une procédure de retour arrière éprouvée.
- **FR-032**: Le changement du mécanisme de déploiement d'un environnement NE DOIT PAS modifier le
  cycle de validation, les autorisations, la provenance ou les preuves attendues.
- **FR-033**: Le système DOIT auditer les changements d'identité, d'affectation, d'autorisation,
  d'espace, de secret, de publication, d'installation et de déploiement.
- **FR-034**: Un événement d'audit DOIT identifier l'acteur, son contexte, l'action, la cible, la
  décision, le résultat, l'heure et une corrélation, sans contenir de secret.
- **FR-035**: Les journaux d'audit DOIVENT être protégés contre la modification non autorisée et
  consultables uniquement selon des mandats explicites.
- **FR-036**: Le système DOIT notifier les personnes concernées des demandes, validations,
  expirations, révocations, mises à jour, échecs et incidents nécessitant une action.
- **FR-037**: Les interfaces critiques DOIVENT rester utilisables sur les équipements courants de
  l'entreprise et dans des conditions de bande passante limitée.
- **FR-038**: Le système DOIT fournir des templates officiels, versionnés et testables permettant
  aux équipes de créer chaque type d'artefact avec les métadonnées et contrôles obligatoires.
- **FR-039**: Une capacité structurante NE DOIT PAS être déclarée opérationnelle avant une mise en
  application factuelle documentant le cas réel, les résultats, les limites et les preuves obtenues.
- **FR-040**: Le premier propriétaire de la plateforme DOIT pouvoir établir lui-même son rôle après
  authentification, au moyen d'une adresse préconfigurée et d'un code à usage unique ; l'opération
  DOIT être atomique, reprenable, auditée et définitivement fermée pour toute autre identité. Après
  réussite, l'état durable en base DOIT permettre de retirer l'adresse et le code du déploiement sans
  interrompre les connexions ; toute nouvelle revendication DOIT rester impossible.

### Key Entities

- **Organizational Unit**: Périmètre configurable du Groupe, avec type, relations et historique.
- **Position Assignment**: Affectation datée d'une personne à un poste ou une responsabilité dans
  un périmètre donné.
- **Principal**: Identité humaine ou technique pouvant demander une action.
- **Workspace**: Espace de collaboration possédant membres, propriétaires, politiques et ressources.
- **Role**: Ensemble nommé de responsabilités, sans portée tant qu'il n'est pas attribué.
- **Permission**: Action élémentaire définie sur un type de ressource.
- **Policy and Grant**: Règle ou attribution reliant principal, rôle, ressource, périmètre,
  environnement, relation, période et conditions.
- **Artifact**: Élément gouverné du patrimoine numérique, indépendamment de son type concret.
- **Artifact Version**: Révision immuable avec provenance, dépendances, compatibilité et preuves.
- **System and Capability**: Système enregistré et fonction métier ou technique qu'il expose.
- **Data Authority**: Attribution explicite d'une catégorie de données à son système de référence.
- **Publication Request**: Demande, contrôles, avis et décisions menant à une publication.
- **Installation**: Version d'un artefact installée pour un bénéficiaire dans un environnement.
- **Environment**: Contexte isolé possédant niveau de risque, politiques, données et accès propres.
- **Secret Reference**: Métadonnées et référence protégée d'un secret conservé hors du catalogue.
- **Approval**: Décision attribuable portant sur une action et un périmètre précis.
- **Audit Event**: Preuve append-only d'une demande, décision ou exécution sensible.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100 % des scénarios d'accès non autorisés de la matrice de référence sont refusés,
  y compris accès direct, recherche, export et appel automatisé.
- **SC-002**: 100 % des décisions d'accès sensibles testées peuvent être expliquées par le rôle,
  le périmètre, la relation, l'environnement et la règle appliquée.
- **SC-003**: Un responsable peut créer un espace, attribuer ses responsabilités et partager un
  premier artefact en moins de 10 minutes sans assistance technique.
- **SC-004**: Au moins 90 % des utilisateurs pilotes trouvent un artefact autorisé adapté à un
  besoin connu en moins de 2 minutes lors du premier essai.
- **SC-005**: Un artefact conforme peut être soumis, validé et publié sans échange manuel hors du
  système ; chaque étape et décision est retrouvable dans l'audit.
- **SC-006**: Toute nouvelle version publiée est détectée par les bénéficiaires concernés dans un
  délai maximal de 24 heures.
- **SC-007**: 100 % des installations pilotes vérifient droits, provenance, intégrité,
  compatibilité et dépendances avant modification de l'environnement cible.
- **SC-008**: Une installation ou un déploiement pilote peut revenir à sa dernière version saine en
  moins de 10 minutes, sans perte de son historique.
- **SC-009**: Aucun secret de production n'est accessible depuis un environnement de revue ou de
  validation dans la batterie de tests de sécurité.
- **SC-010**: 100 % des opérations sensibles retenues par la politique produisent un événement
  d'audit corrélé, consultable par un auditeur autorisé et dépourvu de valeur secrète.
- **SC-011**: Le retrait de toutes les affectations d'une personne supprime ses accès hérités en
  moins d'une minute, sans supprimer les contributions historiques qui doivent être conservées.
- **SC-012**: Une équipe peut remplacer le mécanisme de déploiement d'un environnement pilote sans
  changer le parcours de validation ni les responsabilités des utilisateurs.
- **SC-013**: Les cinq parcours prioritaires sont utilisables sur une connexion à bande passante
  limitée sans perte de données ni double exécution visible.
- **SC-014**: Chaque type d'artefact ouvert aux équipes possède un template approuvé et au moins un
  exemple réel ayant franchi tout son cycle de création, validation, publication et utilisation.

## Assumptions

- La plateforme est initialement réservée aux collaborateurs, stagiaires, prestataires et identités
  techniques explicitement autorisés par KYA.
- Le CVSI administre la plateforme, mais ne reçoit pas automatiquement le droit de lire tous les
  contenus métier confidentiels.
- Les Directions restent propriétaires des méthodes et contenus qu'elles publient ; le CVSI fournit
  les structures, contrôles, plateformes et règles d'industrialisation.
- Les stagiaires disposent d'espaces et d'affectations temporaires avec date de fin obligatoire.
- Les données métier existantes restent dans leurs systèmes autoritaires ; le catalogue conserve
  seulement les métadonnées, références et copies explicitement justifiées.
- Les secrets sont conservés par un service spécialisé distinct du catalogue.
- Les opérations destructrices ou à impact externe exigent une confirmation adaptée au risque.
- La première livraison valide un Skill, un serveur MCP en lecture seule, KYA Platform comme
  premier système réellement enregistré et une application pilote avant l'ouverture à davantage
  d'équipes. Frappe fera l'objet d'un pilote séparé après confirmation de son périmètre métier.
- La conservation des journaux et données sensibles sera fixée par une politique Groupe avant la
  mise en production, avec une valeur par défaut prudente et révisable.
