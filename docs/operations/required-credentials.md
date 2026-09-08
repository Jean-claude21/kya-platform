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

## Correspondance Neon Object Storage

Pour l'implémentation initiale, les cinq paramètres génériques du runtime KYA désignent tous la
même branche Neon Storage :

| Paramètre KYA                          | Valeur Neon Storage attendue                      |
| -------------------------------------- | ------------------------------------------------- |
| `KYA_OBJECT_STORAGE_ENDPOINT_URL`      | endpoint S3 HTTPS de la branche                   |
| `KYA_OBJECT_STORAGE_REGION`            | région S3 fournie pour cet endpoint               |
| `KYA_OBJECT_STORAGE_BUCKET`            | bucket déclaré dans `neon.ts` (`kya-data`)        |
| `KYA_OBJECT_STORAGE_ACCESS_KEY_ID`     | access key S3 générée par Neon pour la branche    |
| `KYA_OBJECT_STORAGE_SECRET_ACCESS_KEY` | secret key S3 associée, lue uniquement au runtime |

`KYA_NEON_API_KEY` et `KYA_NEON_PROJECT_ID` pilotent le control plane Neon ; ils ne remplacent
jamais les deux credentials S3. Development, preview/staging et production utilisent des valeurs
distinctes afin que les fichiers suivent l'isolation des branches Neon.

Avant chaque première connexion réelle, le CVSI reçoit la liste exacte des droits demandés, la
procédure de création, le propriétaire, la durée, le plan de rotation et le test de révocation.
