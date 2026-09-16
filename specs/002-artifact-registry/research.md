# Recherche et décisions — Registre des artefacts

## Standards examinés

- OpenAI décrit un Skill comme un workflow réutilisable fondé sur `SKILL.md`, complété par des
  ressources, modèles, exemples, schémas ou accès à des outils.
- Anthropic définit un Skill comme un dossier avec `SKILL.md` et fichiers de support ; le chargement
  progressif sépare métadonnées, instructions, puis ressources et code. Le dépôt monté appartient à
  la frontière de confiance.
- MCP distingue Tools, Resources et Prompts. Les Tools portent des schémas JSON et sont traités comme
  des déclarations non fiables par le client ; OAuth doit lier le jeton à la ressource ciblée et
  interdire le token passthrough.
- OCI 1.1 et ORAS fournissent une distribution adressée par contenu, avec manifestes, subject et
  referrers adaptés aux signatures, attestations et SBOM.

## Décisions

### R-001 — Paquet de Skill multi-fichiers

KYA adopte le dossier `SKILL.md` + ressources comme unité logique. Le manifeste KYA enveloppe ce
format sans le remplacer. Les profils de cible adaptent seulement l'emplacement d'installation.

### R-002 — Instructions et exécution restent distinctes

Un Skill peut transporter du code déterministe, mais le Registry ne l'exécute jamais. Le code est
une charge utile déclarée, analysée et exécutée uniquement par une cible autorisée. Une capacité
distante ou métier reste un outil d'un serveur MCP.

### R-003 — Métadonnées dans Neon, contenu publié adressé par digest

Neon porte la vérité transactionnelle du catalogue. Git porte le travail humain. Le contenu publié
est identifié par digest et pourra être stocké en OCI ou Object Storage derrière un port ; aucune
dépendance fournisseur n'entre dans le domaine.

### R-004 — Deux manifestes complémentaires

`artifact.manifest.json` décrit identité, provenance, compatibilité, gouvernance et intégrité.
`capability.manifest.json`, requis seulement si le paquet contient des capacités exécutables,
décrit runtimes, points d'entrée, réseau, fichiers, secrets référencés et permissions.

### R-005 — Validation sans extraction dangereuse

La validation travaille d'abord sur un inventaire signé ; l'ingestion d'archive impose limites,
chemins canoniques, absence de fichiers spéciaux, décompression bornée et calcul de digest en flux.

### R-006 — Registry MCP comme façade de contrôle

Le Registry MCP expose découverte et demandes contrôlées. Il ne regroupe pas les outils métier des
autres MCP. Les APIs et le MCP appellent les mêmes services applicatifs.

### R-007 — Autoriser avant de rechercher

Une recherche MCP commence par `ListObjects` dans OpenFGA avec l'unité active explicite. Neon ne
reçoit ensuite que les identifiants internes déjà autorisés. Une liste vide renvoie un résultat vide
sans interroger le catalogue ; la résolution d'un identifiant public précède un contrôle frais sur
l'identifiant interne et ne divulgue jamais l'existence d'un artefact refusé.

### R-008 — Transport MCP 2026 sans session

Le Registry cible MCP `2026-07-28` en Streamable HTTP sans état : un endpoint POST unique, aucune
session de protocole, aucun flux GET autonome. Chaque requête moderne porte
`MCP-Protocol-Version`, `Mcp-Method` et, lorsque requis, `Mcp-Name`, cohérents avec les métadonnées
du corps. Le MCP public historique reste séparé pendant la transition de compatibilité.

### R-009 — Courtier OAuth KYA devant Neon Auth

Neon Auth reste la source d'identité et de session utilisateur, mais son endpoint de projet ne
publie actuellement ni métadonnées RFC 8414/OIDC ni serveur d'autorisation MCP découvrable. KYA
doit donc exposer un courtier OAuth 2.1 : il authentifie l'utilisateur via Neon Auth, émet un jeton
à audience exacte du Registry MCP, applique PKCE et les scopes minimaux, puis publie les métadonnées
requises. Le Registry reste le resource server ; OpenFGA demeure la décision finale par ressource.
Cette frontière doit être livrée avant d'activer le Registry MCP distant.

### R-010 — Installation résolue côté serveur, écriture décidée côté client

Le Registry vérifie la release publiée, sa signature, son digest et la compatibilité de la version
du client, puis retourne un plan typé et déterministe. Il ne renvoie ni commande arbitraire, ni
secret, ni contenu exécutable inline et n'écrit jamais sur le poste. Le client montre la cible,
obtient le consentement, télécharge dans une zone temporaire, revérifie signature et digest, active
atomiquement puis conserve un reçu permettant l'audit et le rollback.

Les profils sont : Codex projet dans `.agents/skills`, Claude Code personnel dans
`~/.claude/skills`, Claude Code projet dans `.claude/skills`, et zip portable dans un répertoire
choisi. L'emplacement personnel Codex reste un symbole résolu par le client
`${CODEX_PERSONAL_SKILLS_DIR}` : l'API OpenAI expose aussi la création et les versions immuables de
Skills, mais ne garantit pas un chemin local universel pour tous les environnements Codex.

## Références primaires

- OpenAI Academy, « Using skills » : https://openai.com/academy/skills/
- Claude Platform, « Agent Skills » :
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- MCP, « Streamable HTTP » :
  https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http
- MCP, « Authorization » :
  https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization
- MCP, « Authorization Server Discovery » :
  https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/authorization-server-discovery
- ORAS, « Understanding OCI artifacts » : https://oras.land/docs/1.2/concepts/artifact/
- OCI, « Image and Distribution Specs v1.1 » :
  https://opencontainers.org/posts/blog/2024-03-13-image-and-distribution-1-1/
