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

## Références primaires

- OpenAI Academy, « Using skills » : https://openai.com/academy/skills/
- Claude Platform, « Agent Skills » :
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- MCP, « Tools » : https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- MCP, « Authorization » :
  https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- ORAS, « Understanding OCI artifacts » : https://oras.land/docs/1.2/concepts/artifact/
- OCI, « Image and Distribution Specs v1.1 » :
  https://opencontainers.org/posts/blog/2024-03-13-image-and-distribution-1-1/
