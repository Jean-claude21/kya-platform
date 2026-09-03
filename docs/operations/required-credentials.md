# Clés et identités techniques requises

Ce document inventorie les accès attendus sans jamais enregistrer leur valeur. Les valeurs seront
créées dans Infisical et injectées au runtime avec le moindre privilège.

## État actuel

Aucune clé externe n'est requise pour le socle local, les contrats et les tests. Les tests utilisent
des instances locales ou des adapters simulés.

## Demande juste à temps

| Étape               | Accès à fournir                             | Finalité                         | Séparation obligatoire        |
| ------------------- | ------------------------------------------- | -------------------------------- | ----------------------------- |
| Persistance Neon    | URL poolée runtime + URL directe migrations | API et Alembic                   | preview, test, production     |
| Identité            | URL Neon Auth, issuer, audience et JWKS     | sessions et jetons               | par branche/environnement     |
| Fichiers            | identité S3 Neon Object Storage             | objets privés et publications    | par branche/environnement     |
| Autorisation        | store/model OpenFGA + identité machine      | décisions serveur                | par environnement             |
| Secrets             | identité machine Infisical                  | lecture de références autorisées | par workload et environnement |
| Synchronisation     | GitHub App ID, installation ID, clé privée  | dépôts, PR, tags et manifestes   | permissions minimales         |
| Déploiement         | jeton Dokploy et/ou Coolify                 | preview, promotion, rollback     | par fournisseur/environnement |
| Frappe              | identité d'intégration Frappe               | capacités et données autorisées  | par site et périmètre         |
| Modèle IA optionnel | clé Z.AI ou abonnement compatible           | GLM-5.3 via adapter              | personnel, pilote, production |

Avant chaque première connexion réelle, le CVSI reçoit la liste exacte des droits demandés, la
procédure de création, le propriétaire, la durée, le plan de rotation et le test de révocation.
