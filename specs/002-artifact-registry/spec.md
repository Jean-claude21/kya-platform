# Feature Specification: Registre des artefacts KYA

**Feature Branch**: `feat-artifact-registry`

**Created**: 2026-09-06

**Status**: Approved for implementation

**Input**: Construire le catalogue gouverné permettant aux Directions de créer, valider, publier,
découvrir et distribuer des Skills complets, serveurs MCP, applications et connecteurs.

## User Scenarios & Testing

### User Story 1 - Créer un Skill complet (Priority: P1)

Un contributeur autorisé crée un Skill dans son espace à partir d'un paquet contenant `SKILL.md`
et, selon le besoin, scripts, références, modèles, schémas, exemples et tests. Le système valide le
paquet sans exécuter son code.

**Independent Test**: soumettre le manifeste et l'inventaire d'un Skill multi-fichiers valide,
puis constater un brouillon consultable ; soumettre un paquet dangereux ou incomplet et constater
un refus explicable.

**Acceptance Scenarios**:

1. **Given** un contributeur autorisé, **When** il soumet un manifeste, une provenance Git et un
   inventaire conformes, **Then** un artefact brouillon et sa version sont créés atomiquement.
2. **Given** un Skill contenant du code, **When** ses entrées, permissions, dépendances ou tests ne
   sont pas déclarés, **Then** la candidature est refusée avant stockage publiable.
3. **Given** un paquet, **When** il contient un chemin absolu, une traversée `..`, un lien symbolique
   sortant ou une valeur secrète détectable, **Then** l'import échoue fermé.

### User Story 2 - Valider et publier avec séparation des responsabilités (Priority: P1)

La Direction propriétaire valide le fond, le CVSI valide les risques techniques et un approbateur
habilité autorise la publication d'une version immuable.

**Independent Test**: conduire un Skill de brouillon à publié avec trois identités distinctes et
vérifier que l'auteur ne peut pas s'auto-approuver.

**Acceptance Scenarios**:

1. **Given** une version candidate, **When** les contrôles obligatoires et les décisions requises
   sont positifs, **Then** la version signée devient publiable par son digest.
2. **Given** une preuve manquante ou expirée, **When** la publication est demandée, **Then** elle est
   bloquée et la cause est auditée.
3. **Given** une version publiée, **When** son tag source change, **Then** le digest approuvé reste
   l'unique référence installable.

### User Story 3 - Découvrir seulement ce qui est autorisé (Priority: P1)

Un collaborateur recherche depuis l'interface ou le Registry MCP. Les résultats, détails, versions
et outils exposés sont filtrés par identité, unité active, espace, rôle et environnement.

**Independent Test**: effectuer la même recherche avec deux identités de périmètres différents et
prouver qu'aucun identifiant masqué ne fuit dans les résultats, compteurs ou erreurs.

### User Story 4 - Installer ou mettre à jour dans un environnement IA (Priority: P2)

Un utilisateur sélectionne une version compatible et demande son installation dans Codex, Claude
Code ou un autre environnement pris en charge. Le système prépare un paquet adapté, vérifie son
intégrité et trace l'opération ; le client garde la décision finale d'écriture locale.

**Independent Test**: résoudre un Skill publié vers deux cibles, produire les plans adaptés sans
secret, puis confirmer l'installation et la détection d'une mise à jour.

### User Story 5 - Enregistrer un serveur MCP ou une application (Priority: P2)

Le CVSI enregistre un serveur MCP, ses outils et ses contrats, ou une application, ses interfaces et
ses environnements, dans le même catalogue sans confondre le plan de contrôle et l'exécution.

**Independent Test**: enregistrer un MCP en lecture seule et vérifier que ses outils, scopes,
niveaux de risque et URL d'environnement sont cohérents et distincts de ceux d'un Skill.

## Edge Cases

- Deux propriétaires tentent de créer le même identifiant stable.
- Une version SemVer existe déjà avec un contenu différent.
- Le dépôt devient inaccessible après validation ou le commit est supprimé.
- Une archive contient une bombe de décompression, des doublons de casse ou des fichiers interdits.
- Une dépendance est suspendue, révoquée, incompatible ou forme un cycle.
- Un Skill déclaratif devient exécutable dans une nouvelle version.
- Une autorisation change entre la recherche et l'installation.
- Un utilisateur demande « latest » alors qu'une version approuvée est suspendue.
- Une cible ne prend pas en charge les scripts, le langage ou le format du paquet.

## Functional Requirements

- **FR-001**: Le registre DOIT gérer au minimum Skill, MCP server, MCP tool, application, connector,
  API, data product, template, policy et design system sous un modèle commun extensible.
- **FR-002**: Chaque artefact DOIT posséder un identifiant KYA stable, un slug, un nom, un résumé,
  un propriétaire métier, un responsable technique et un workspace propriétaire.
- **FR-003**: Chaque version DOIT référencer un commit Git immuable, un chemin source, un digest du
  contenu, un digest du manifeste, une version SemVer et un inventaire complet des fichiers.
- **FR-004**: Un Skill DOIT contenir un `SKILL.md` avec frontmatter `name` et `description` compatible
  avec le profil de portabilité KYA.
- **FR-005**: Un Skill PEUT contenir scripts, références, modèles, schémas, exemples, tests et assets.
- **FR-006**: La présence de code, binaire, macro, dépendance ou accès réseau DOIT être classifiée et
  déclarée ; elle augmente les contrôles requis sans transformer le Skill en outil MCP.
- **FR-007**: Le registre NE DOIT jamais exécuter le contenu d'un paquet pendant ingestion,
  validation, recherche ou distribution.
- **FR-008**: Le système DOIT refuser chemins non relatifs, traversées, liens sortants, fichiers
  spéciaux, archives ambiguës et dépassements de taille/nombre configurés.
- **FR-009**: Chaque fichier DOIT avoir chemin canonique, type média, taille et digest SHA-256.
- **FR-010**: Une version publiée DOIT être immuable et adressable par digest ; un tag est seulement
  un pointeur convivial et ne constitue pas une preuve d'intégrité.
- **FR-011**: Les attestations DOIVENT couvrir provenance, tests, analyse de dépendances, secrets,
  licence, compatibilité, sécurité et validation métier selon le risque.
- **FR-012**: Les artefacts exécutables DOIVENT produire une SBOM et déclarer points d'entrée,
  runtime, commandes, permissions, réseau, système de fichiers, secrets référencés et limites.
- **FR-013**: Les secrets DOIVENT rester dans Infisical ; le registre ne conserve que des références
  typées et non résolubles par les lecteurs du catalogue.
- **FR-014**: Neon DOIT être la source autoritaire des métadonnées, versions, fichiers, validations,
  publications, installations et révocations du registre.
- **FR-015**: Git DOIT rester la source de travail et de revue ; un stockage d'artefacts adressé par
  contenu DOIT porter les paquets publiés lorsque la distribution binaire est activée.
- **FR-016**: Toute lecture et écriture DOIT être filtrée côté serveur via OAuth et OpenFGA avec une
  unité active explicite et une autorisation fraîche avant action.
- **FR-017**: La recherche NE DOIT interroger l'index qu'avec la liste des artefacts préautorisés.
- **FR-018**: Les outils MCP visibles DOIVENT pouvoir être réduits selon les scopes et autorisations
  de l'appelant ; les écritures exigent confirmation et clé d'idempotence.
- **FR-019**: La publication DOIT appliquer séparation auteur, relecteur et approbateur pour les
  risques contrôlé, sensible et administratif.
- **FR-020**: Une installation DOIT résoudre dépendances, compatibilité, politique, provenance,
  signature et digest avant de produire un plan de modification.
- **FR-021**: L'installation dans un environnement utilisateur DOIT être consentie par celui-ci ; le
  serveur ne doit pas écrire silencieusement sur son poste.
- **FR-022**: Chaque installation DOIT conserver cible, version épinglée, état, dernière vérification,
  historique, résultat et version de retour arrière.
- **FR-023**: Les mises à jour DOIVENT être vérifiées quotidiennement et classées par compatibilité,
  risque, urgence et besoin d'approbation.
- **FR-024**: Suspension ou révocation DOIT retirer immédiatement une version des nouvelles
  installations et notifier les installations existantes concernées.
- **FR-025**: Chaque opération sensible DOIT produire audit et événement outbox sans contenu secret.
- **FR-026**: Les API et outils MCP DOIVENT employer les mêmes services de domaine et contrats.
- **FR-027**: Le système DOIT fournir des profils d'export distincts pour Codex, Claude Code et zip
  portable, sans prétendre à une compatibilité non testée.
- **FR-028**: Le premier pilote DOIT être un Skill KYA multi-fichiers réel ayant franchi création,
  validation, publication, découverte et résolution d'installation.

## Key Entities

- **Artifact**: identité et gouvernance durables d'une capacité numérique.
- **Artifact Version**: version candidate ou publiée et immuable d'un artefact.
- **Package File**: entrée canonique de l'inventaire avec digest, taille, type et classification.
- **Capability Declaration**: comportements exécutables et permissions demandées.
- **Dependency Constraint**: dépendance vers un artefact et plage de versions.
- **Attestation**: preuve typée produite par un contrôle ou une validation humaine.
- **Release**: version publiée, signée, suspendable ou révocable.
- **Installation Target/Profile**: environnement destinataire et règles d'adaptation.
- **Installation**: état d'une release installée sur une cible.
- **Distribution Plan**: résultat déterministe et consenti avant toute écriture locale.

## Measurable Outcomes

- **SC-001**: 100 % des paquets malveillants de la batterie de référence sont refusés avant
  publication et sans exécution de contenu.
- **SC-002**: 100 % des recherches de la matrice négative ne révèlent aucun artefact non autorisé.
- **SC-003**: Un Skill multi-fichiers conforme est créé en moins de 3 minutes et publié sans échange
  hors plateforme une fois les approbateurs disponibles.
- **SC-004**: 100 % des versions publiées sont reproductibles par commit et vérifiables par digest.
- **SC-005**: Un utilisateur résout un Skill autorisé vers Codex ou Claude Code en moins de 60
  secondes, hors téléchargement réseau.
- **SC-006**: 100 % des mutations rejouées avec la même clé d'idempotence ont le même résultat.
- **SC-007**: p95 inférieur à 500 ms pour lecture catalogue et 1 s pour recherche au volume pilote.

## Assumptions

- Les artefacts sont privés à KYA par défaut.
- GitHub héberge les sources initiales ; OCI/object storage est introduit derrière un port.
- Les fichiers publiés sont limités initialement à 100 MiB et 2 000 entrées par paquet.
- Le code d'un Skill est exécuté uniquement par une cible approuvée et sandboxée, jamais par le
  Registry.
- La synchronisation directe avec les APIs propriétaires de Skills viendra après le premier export
  portable testé.
