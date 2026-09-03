# ADR 0001 — FastAPI comme backend métier unique

- **Statut** : accepté
- **Date** : 2026-09-03
- **Décideur** : CVSI KYA-Energy Group

## Contexte

La plateforme doit protéger Neon, les secrets, les autorisations fines, l'audit, les publications,
les outils MCP et les déploiements. Une interface TanStack seule ne constitue pas une frontière de
confiance suffisante. Maintenir en parallèle une API métier TypeScript et une API Python créerait
deux implémentations des mêmes règles.

## Décision

FastAPI devient l'unique backend métier. Le même package Python expose trois processus logiques :

1. API HTTP versionnée ;
2. Registry MCP protégé ;
3. workers et routines planifiées.

TanStack reste responsable de l'expérience utilisateur et intègre Neon Auth. FastAPI valide les
jetons Neon Auth par issuer, audience et JWKS, puis demande les décisions d'autorisation à OpenFGA. SQLAlchemy 2 et
Alembic deviennent l'unique couche de persistance vers Neon.

## Conséquences

- aucune clé fournisseur ni connexion Neon n'est exposée au navigateur ;
- les règles métier sont testées une seule fois avec pytest ;
- l'API, le MCP et les workers peuvent être déployés séparément sans devenir des microservices ;
- les contrats Web sont générés depuis OpenAPI/JSON Schema ;
- Hono et Drizzle ne portent plus de logique métier ni de migrations.

## Garde-fous

- dépendances dirigées `transport → application → domain` ;
- adapters fournisseurs derrière des ports ;
- refus par défaut et contrôle OpenFGA au moment de chaque action ;
- migrations immuables après publication ;
- tests de contrats, politiques, sécurité et intégration avant promotion.
