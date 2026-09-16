# Spécification — Suivi MCP des collectes v0.1

## Résultat attendu

Après avoir déclenché une ingestion depuis Claude, ChatGPT ou un autre client MCP, le
collaborateur peut suivre la même exécution jusqu'à son résultat terminal. Il reçoit un bilan
structuré et exploitable par l'IA : état, dates, erreur stable éventuelle, preuve produite et
résultats qualité. Aucun secret ni emplacement de stockage n'est exposé.

## Parcours concret

1. `start_ingestion` crée une exécution durable et renvoie son `run_id`.
2. Le worker exécute le connecteur déterministe en arrière-plan.
3. `get_ingestion_run` utilise ce `run_id` pour lire l'état courant.
4. Une exécution terminée renvoie le snapshot et ses contrôles qualité.
5. Une exécution échouée renvoie un code d'erreur stable, sans détail sensible.

## Exigences

- **FR-001** — La lecture exige `data:read` et `org_unit.can_view`.
- **FR-002** — Le run doit appartenir à l'unité active issue du jeton OAuth.
- **FR-003** — Le dépôt agrège run, clé du pipeline, snapshot et qualité en une lecture gouvernée.
- **FR-004** — La réponse n'expose ni fournisseur, ni conteneur, ni clé d'objet, ni secret.
- **FR-005** — Chaque appel est audité avec acteur, unité, cible et corrélation.
- **FR-006** — L'absence d'audit ou d'autorisation ferme l'accès.
- **FR-007** — Les réponses utilisent des schémas Pydantic stricts.
- **FR-008** — L'outil rejoint la passerelle MCP existante ; aucune nouvelle clé utilisateur.

## Outil

| Outil               | Portée OAuth | Autorisation        | Résultat                |
| ------------------- | ------------ | ------------------- | ----------------------- |
| `get_ingestion_run` | `data:read`  | `org_unit.can_view` | état, preuve et qualité |

## Hors périmètre

- lecture du contenu physique du snapshot ;
- journal technique interne ou stack trace ;
- annulation et relance automatique ;
- notification proactive de fin de traitement.

## Critères d'acceptation

- un run visible est restitué avec son pipeline et son état ;
- un run terminé contient le résumé du snapshot et les résultats qualité ;
- un run d'une autre unité est indistinguable d'un run absent ;
- aucun chemin de stockage n'est sérialisé ;
- les tests MCP, dépôt, typage, lint et suite backend restent verts.
