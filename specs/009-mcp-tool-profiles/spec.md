# Spécification — Profils d'outils MCP gouvernés v0.1

**Branche** : `feat-mcp-tool-profiles`  
**Date** : 2026-09-08  
**Statut** : prêt pour implémentation

## Scénarios utilisateurs

### US1 — Une boîte à outils pertinente avec une seule connexion (P1)

Un collaborateur connecte une seule fois Claude, ChatGPT ou son éditeur à KYA Platform. La liste
retournée contient uniquement les outils permis par ses scopes, son rôle, son unité active et son
profil courant.

**Test indépendant** : deux utilisateurs utilisant le même client OAuth et la même URL MCP
obtiennent des listes différentes selon leurs droits, sans fuite de nom d'outil interdit.

### US2 — Réduire volontairement les outils visibles (P1)

Un collaborateur désactive depuis KYA Platform les outils inutiles dans son contexte. La préférence
réduit la liste au prochain `tools/list`, sans pouvoir activer un outil non autorisé.

**Test indépendant** : désactiver un outil autorisé le masque et interdit aussi son appel direct ;
supprimer la préférence rétablit l'héritage.

### US3 — Administrer des profils réutilisables (P2)

Le CVSI prépare des profils bornés tels que `registry-reader`, `data-reader`, `data-operator` et
`catalog-publisher`, puis les attribue à une unité, un rôle, une équipe ou une personne.

**Test indépendant** : une affectation active modifie le calcul effectif ; son expiration ou sa
révocation est prise en compte sans reconnecter le client.

## Cas limites

- Une panne de Neon ou OpenFGA renvoie une liste vide et refuse l'appel.
- Une préférence `enabled` ne dépasse jamais les profils, scopes ou autorisations hérités.
- Un `disabled` explicite gagne sur tous les profils qui activent le même outil.
- Une révision concurrente est refusée ; aucune mise à jour perdue n'est acceptée.
- Le dépassement de 24 outils est refusé, jamais tronqué silencieusement.
- Un changement d'unité active recalcule entièrement la liste.
- Un outil retiré ou sans handler actif n'est jamais annoncé.
- Les Skills restent des artefacts installables et ne deviennent jamais des outils MCP.

## Exigences fonctionnelles

- **FR-001** — Conserver une seule URL MCP et une seule famille de jetons par client.
- **FR-002** — Calculer l'ensemble effectif par intersection des outils actifs, scopes OAuth,
  autorisations OpenFGA, profils applicables et préférences restrictives.
- **FR-003** — Réautoriser chaque `tools/call`, même si l'outil figurait dans un ancien `tools/list`.
- **FR-004** — Stocker définitions, profils, éléments, affectations et préférences sans secret.
- **FR-005** — Rendre les listes déterministes et limitées à 24 outils.
- **FR-006** — Appliquer `disabled` comme refus prioritaire et `DELETE` comme retour à l'héritage.
- **FR-007** — Publier les modifications avec contrôle de révision et audit append-only.
- **FR-008** — Ne jamais encoder profil ou liste d'outils dans le jeton OAuth.
- **FR-009** — Fournir une lecture de l'état effectif et de ses sources non sensibles via HTTP.
- **FR-010** — Livrer d'abord un mode shadow comparant l'ensemble historique et le nouvel ensemble,
  puis activer l'enforcement uniquement après divergence comprise.
- **FR-011** — La sélection de profil ne remplace jamais l'autorisation sur la ressource métier.
- **FR-012** — La prochaine requête stateless doit refléter une révocation ou une préférence modifiée.

## Entités

- **ToolDefinition** : déclaration autoritative d'un handler MCP actif et de son risque.
- **ToolProfile** : ensemble réutilisable, versionné et borné d'outils.
- **ToolProfileItem** : activation ou désactivation explicite d'un outil dans un profil.
- **ToolProfileAssignment** : attribution temporelle d'un profil à un sujet et un contexte.
- **UserToolPreference** : réduction personnelle par unité et, si utile, par client OAuth.
- **EffectiveToolSet** : résultat calculé non persistant, accompagné d'une révision et de sources.

## Critères de réussite

- **SC-001** — Aucun outil hors scope, profil ou permission n'apparaît ni ne peut être appelé.
- **SC-002** — `tools/list` reste sous 200 ms à chaud et 500 ms à froid au périmètre pilote.
- **SC-003** — Une modification est visible à la requête suivante, sans nouvelle connexion.
- **SC-004** — Le calcul utilise au plus une opération OpenFGA de liste par requête.
- **SC-005** — Les tests couvrent unité, client, révocation, expiration, refus explicite et panne.

## Hors périmètre v0.1

- créer une URL MCP par profil ;
- charger dynamiquement du code d'outil depuis le catalogue ;
- laisser un agent modifier seul son profil ;
- dépendre des notifications pour garantir la cohérence ;
- exposer les raisons sensibles d'un refus OpenFGA.
