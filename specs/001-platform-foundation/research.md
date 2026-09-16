# Recherche et décisions — Fondation KYA Platform

**Date**: 2026-09-03  
**Statut**: choix approuvés le 2026-09-03, adoption de production conditionnée par les preuves du pilote

## Règle de décision

Une technologie n'est retenue que si elle sert un besoin KYA, possède une documentation et un
cycle de maintenance vérifiables, peut être automatisée et reste remplaçable derrière un contrat.
Les chiffres marketing ne constituent pas une preuve. Chaque choix doit réussir le quickstart et
les tests de conformité avant d'être qualifié pour la production.

## D01 — Architecture du dépôt

**Décision**: monorepo polyglotte. pnpm/Turborepo gouverne le Web TypeScript ; uv gouverne le
backend Python. Le noyau FastAPI contient les modules métier et expose plusieurs points d'entrée
déployables sans dupliquer les règles.

**Rationale**: livraison rapide, contrats partagés, changements atomiques et extraction ultérieure
possible. Les limites sont contrôlées par les imports, tests de contrat et propriétaires de code.

**Alternatives considérées**: microservices et dépôts séparés dès le départ, rejetés car ils
multiplient CI, versions et opérations avant que les frontières réelles soient validées.

## D02 — Runtime et surfaces applicatives

**Décision**: Python 3.14 et FastAPI portent l'API métier, le Registry MCP et les workers. Node.js 24
LTS et TypeScript strict portent TanStack Start et la frontière de session. Le Registry utilise le
SDK Python MCP et Streamable HTTP ; le mode stdio est réservé aux usages locaux approuvés.

**Rationale**: FastAPI donne une frontière serveur explicite pour Neon, secrets, audit et
autorisations, tout en restant naturel pour les traitements data/IA. Les surfaces API, MCP et worker
partagent le même domaine Python, mais restent exécutables et dimensionnables séparément.

**Alternatives considérées**: API uniquement dans l'application Web, rejetée pour préserver les
contrats externes ; microservice MCP indépendant dès le premier jour, différé jusqu'à preuve d'un
cycle de déploiement distinct.

## D03 — Données et migrations

**Décision**: Neon Postgres est autoritaire pour le Hub. SQLAlchemy 2 fournit les modèles et accès
asynchrones ; Alembic produit des migrations SQL révisables. La connexion poolée sert le runtime et
une connexion directe dédiée sert les migrations. Les migrations publiées sont immuables.

**Rationale**: Neon fournit des branches isolées adaptées aux previews ; SQLAlchemy/Alembic est le
couple natif du backend Python et évite une seconde couche de persistance en TypeScript.

**Alternatives considérées**: Prisma, valide mais moins direct pour les politiques et SQL avancé ;
accès SQL libre depuis chaque module, rejeté pour préserver les frontières.

## D04 — Authentification et identités

**Décision**: Neon Auth gère utilisateurs, sessions, organisations, OAuth et émission des JWT dans
le schéma branchable `neon_auth`. FastAPI valide chaque jeton par émetteur, audience, signature
JWKS et expiration, puis demande la décision métier à OpenFGA. Les identités KYA sont liées par
couple immuable émetteur/sujet.

**Rationale**: l'identité suit les branches de preview avec Postgres, sans synchronisation externe.
Neon Auth authentifie ; OpenFGA reste l'autorité des relations et permissions fines KYA.

**Alternatives considérées**: Better Auth direct est redondant car Neon Auth l'intègre déjà ;
Keycloak est différé tant que fédération et exploitation HA ne sont pas établies ; comptes maison,
rejetés.

## D05 — Autorisation fine

**Décision**: OpenFGA est le moteur de décision ReBAC. Les rôles KYA se traduisent en relations et
permissions ; les périmètres, sessions actives et dates sont fournis par tuples contextuels ou
conditions. Neon conserve les objets métier, attributions, explications et audit ; le modèle FGA
est versionné et testé dans Git.

**Rationale**: les espaces partagés, multi-affectations, projets transversaux et héritages sont des
relations, pas seulement des rôles. OpenFGA documente le contexte multi-organisation, les conditions
et les requêtes de liste filtrées par permission.

**Alternatives considérées**: Cedar, très bon pour RBAC/ABAC mais demandant davantage de préparation
des entités ; OPA, généraliste mais moins naturel pour les graphes de partage ; tables RBAC seules,
rejetées. Un benchmark factuel décidera si OpenFGA reste externe ou est simplifié pour le pilote.

## D06 — Secrets et clés

**Décision**: Infisical est le gestionnaire initial. Le Hub ne conserve que `SecretReference`,
propriétaire, portée, finalité, environnement, rotation et état. Les workloads utilisent des
identités machines et jetons courts. Les secrets de preview, test et production sont distincts.

**Rationale**: Infisical fournit projets, environnements, rôles, identités machines, rotation et
audit avec une exploitation plus accessible au démarrage. L'accès aux valeurs ne transite pas par
le navigateur ni par les journaux du Hub.

**Alternatives considérées**: Vault reste le candidat pour secrets dynamiques, PKI ou exigences
fortes futures ; stockage chiffré dans Neon et secrets GitHub comme source globale sont rejetés.

## D07 — Catalogue, distribution et templates

**Décision**: tout élément distribuable possède un manifeste KYA signé décrivant identité, type,
version, provenance, somme de contrôle, propriétaire, compatibilité, dépendances, scopes, canal et
preuves. Des templates officiels existent pour Skill, MCP, application et connecteur.

**Rationale**: un contrat commun rend la recherche, la validation, l'installation, la mise à jour et
le retrait déterministes. GitHub contient le source ; Neon contient l'état gouverné et consultable.

**Alternatives considérées**: déduire toutes les métadonnées du code ou accepter des archives libres,
rejeté car non fiable et difficile à auditer.

## D08 — MCP et autonomie IA

**Décision**: le Registry MCP découvre et demande ; il n'exécute pas arbitrairement un Skill. Les
Skills fournissent méthode et contexte, les outils MCP exécutent des capacités. Chaque outil possède
schéma d'entrée/sortie, scopes, niveau de risque, idempotence et règle de confirmation.

**Rationale**: le SDK officiel sépare vérification du jeton, contexte d'identité et contrôle par
outil. Les serveurs distants suivent OAuth et Protected Resource Metadata. Les outils d'écriture
recalculent toujours l'autorisation au moment de l'exécution.

**Alternatives considérées**: un MCP omnipotent routant tout et chargement dynamique de code depuis
le catalogue, rejetés pour raisons de sécurité et de rayon d'impact.

## D09 — Branches, versions et promotions

**Décision**: `feat-xxx` part de `dev` et revient par Pull Request ; `dev` rejoint `main` par Pull
Request de livraison. Tout commit accepté sur `main` reçoit un tag SemVer annoté et immuable. Les
tags `vX.Y.Z-dev.N` sont réservés aux jalons `dev` réellement déployables.

**Rationale**: la convention demandée sépare travail, intégration et stable. Les tags représentent
des preuves de livraison, pas des marqueurs décoratifs.

**Alternatives considérées**: trunk-based, plus simple mais contraire à la gouvernance retenue ; tag
sur chaque commit `dev`, rejeté car il rend les versions illisibles.

## D10 — Dokploy et Coolify

**Décision**: un contrat `DeploymentProvider` masque les différences. Une cible choisit exactement
un fournisseur primaire ; le double déploiement n'est utilisé que pour un test de portabilité ou un
plan de reprise approuvé. Les deux fournisseurs doivent réussir la même suite de conformité.

**Rationale**: Dokploy et Coolify proposent previews liées aux Pull Requests et déploiements par
branche. Coolify documente explicitement les secrets de preview séparés. Deux adaptateurs réduisent
le verrouillage ; deux productions actives sans orchestration augmenteraient le risque.

**Alternatives considérées**: imposer un fournisseur unique avant benchmark, rejeté ; utiliser les
deux simultanément pour chaque version, rejeté hors haute disponibilité conçue et testée.

## D11 — Pipeline et chaîne d'approvisionnement

**Décision**: les Pull Requests exécutent formatage, types, tests, analyse de dépendances, secrets,
construction et attestations avant preview. L'image est construite une fois, identifiée par digest,
puis promue. Les previews reçoivent une branche Neon dédiée et des secrets limités.

**Rationale**: promouvoir le même artefact évite les différences entre test et production. Une
preview exécute du code non encore approuvé et doit donc être traitée comme non fiable.

**Alternatives considérées**: reconstruire à chaque environnement ou injecter les secrets de
production dans les previews, rejeté.

## D12 — Backend FastAPI et propriété de la logique

**Décision**: FastAPI est l'unique backend métier. Le navigateur et le BFF TanStack ne disposent
d'aucun accès direct à Neon, OpenFGA, Infisical ou aux clés fournisseurs. API, MCP et workers
appellent les mêmes cas d'usage Python ; ils ne réimplémentent aucune règle métier.

**Rationale**: cette séparation réduit la surface de secrets, facilite les traitements data/IA et
permet des tests pytest identiques quel que soit le canal d'entrée. Elle conserve une extraction
future possible sans payer dès maintenant le coût de microservices.

**Alternatives considérées**: deux backends Hono/FastAPI, rejetés pour éviter divergence et double
maintenance ; accès Neon depuis TanStack, rejeté car la sécurité ne doit pas dépendre du navigateur.

## D13 — Fichiers et Neon Object Storage

**Décision**: Neon Object Storage est l'adaptateur pilote du port S3 `ObjectStorage` pour fichiers,
aperçus, preuves et bundles. GitHub reste l'autorité du code, Postgres celle des métadonnées et
Infisical celle des secrets. Aucun objet critique ne dépend d'une copie unique tant que le service
est en bêta.

**Rationale**: les objets suivent les branches Neon, ce qui rend les previews cohérentes. Le port
S3 maintient la possibilité de migrer vers un fournisseur compatible sans modifier le domaine.

**Alternatives considérées**: stocker les blobs dans Postgres, rejeté ; coupler le domaine aux API
Neon, rejeté ; ignorer Storage, rejeté car les artefacts et leçons comportent des fichiers.

## Décisions validées et contrôles différés

Ces choix ont été approuvés. Leur conformité opérationnelle sera encore démontrée avant production :

1. **Identité** — Neon Auth est retenu ; FastAPI consomme seulement son contrat JWT/JWKS et OpenFGA
   conserve l'autorisation KYA.
2. **Gestionnaire de secrets** — proposition : Infisical pour le pilote ; passage à Vault seulement
   si les secrets dynamiques, la PKI ou une exigence réglementaire le justifient.
3. **Déploiement primaire** — proposition : benchmark identique Dokploy/Coolify, puis choix d'un
   primaire par environnement ; ne jamais les faire écrire simultanément sur la même production.
4. **OpenFGA** — proposition : le valider sur une matrice KYA comprenant Direction, équipe, projet,
   stagiaire, délégation, interdiction, expiration et accès MCP avant adoption définitive.
