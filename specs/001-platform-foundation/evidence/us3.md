# US3 — Catalogue et distribution gouvernés

Date de contrôle : 2026-09-04  
État : implémentation T040–T046 terminée ; preuve bout-en-bout T047 encore ouverte.

## Garanties automatisées

- La recherche demande d'abord à l'autorisation la liste des identifiants visibles. L'index ne
  reçoit aucun appel lorsque cette liste est vide et toute réponse hors périmètre est rejetée.
- Les contrats MCP refusent les champs non déclarés. Les écritures exigent confirmation explicite
  et clé d'idempotence d'au moins 16 caractères.
- Un scope OAuth absent interrompt le contrôle avant l'appel de politique. Un scope présent ne
  remplace jamais le droit KYA sur la ressource.
- L'installation vérifie l'intégrité et la compatibilité. Les changements majeurs exigent une
  approbation. Le rollback ne restaure que la dernière version saine connue.
- Le contrôle quotidien est idempotent et classe les mises à jour sans les installer implicitement.
- Le serveur Registry utilise le SDK MCP Python officiel 2.1.1, sept outils typés et le transport
  Streamable HTTP. L'identité Neon Auth est adaptée sans propager les claims privés.
- Un Skill reste un artefact versionné à charger ; aucun outil MCP ne l'exécute.

## Résultats

```text
Backend : 136 tests réussis · couverture 92,10 %
Registry MCP ciblé : 11 tests réussis
Interface Catalogue : 6 tests composants réussis (ensemble web)
Build : client et SSR réussis
Typage/lint ciblés : réussis
```

L'environnement local utilise Node 22.14 alors que le dépôt exige Node 24 ou plus. pnpm émet donc
un avertissement ; les tests et builds réussissent, mais la validation de release devra employer
l'image Node 24 verrouillée par le projet.

## Contrôle navigateur

- Navigation Catalogue et structure ARIA vérifiées.
- À 601 px : largeur du document 586 px, aucun débordement horizontal.
- À 1 440 px : colonnes 230 px / 780 px / 340 px, aucun débordement horizontal.
- Les données sont explicitement marquées comme démonstration et les écritures non connectées sont
  désactivées.
- Le service de capture d'image n'a pas rendu de capture ; aucune preuve visuelle PNG n'est donc
  revendiquée.

## Condition de clôture T047

T047 ne sera cochée qu'après branchement des adaptateurs Neon/OpenFGA et exécution du même scénario
install → update → rollback depuis l'interface et depuis un client MCP OAuth, avec identifiants,
digests, événements d'audit et résultat négatif d'un utilisateur non autorisé.
