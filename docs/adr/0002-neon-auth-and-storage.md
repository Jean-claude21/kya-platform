# ADR 0002 — Neon Auth et Object Storage branchables

- **Statut** : accepté
- **Date** : 2026-09-03
- **Décideur** : CVSI KYA-Energy Group

## Décision

Neon fournit le socle branchable de KYA Platform : Postgres, Neon Auth et Object Storage. Chaque
preview reçoit des données, une identité et des fichiers isolés. FastAPI reste l'unique frontière
métier et ne délègue pas ses décisions d'autorisation à l'interface.

Neon Auth authentifie les personnes et émet les jetons. FastAPI valide issuer, audience, signature
JWKS et expiration. OpenFGA décide ensuite si le principal peut agir sur la ressource et la portée.

Neon Object Storage implémente un port S3 remplaçable. Il conserve les fichiers et bundles, jamais
le code source, les métadonnées d'autorité ou les valeurs secrètes. Durant sa bêta, les objets
critiques conservent une stratégie de copie et de restauration indépendante.

## Conséquences

- Better Auth n'est pas installé directement par KYA Platform ;
- les identités de preview suivent les branches Neon ;
- TanStack ne reçoit aucune connexion PostgreSQL ;
- la Data API n'est pas une voie métier parallèle à FastAPI ;
- les clés Object Storage restent dans Infisical et ne transitent pas par le catalogue.
