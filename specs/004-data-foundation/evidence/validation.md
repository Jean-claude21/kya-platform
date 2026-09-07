# Preuves de validation — 7 septembre 2026

## Qualité backend

- Ruff : réussi ;
- formatage Ruff : réussi ;
- mypy : 107 fichiers, aucune erreur ;
- pytest : 411 tests réussis ;
- couverture : 90,03 %, seuil de 90 % respecté.

## Migration Neon

La migration `20260907_0011` a été testée sur une branche Neon éphémère non protégée :

1. montée de la chaîne jusqu'à `0011` ;
2. descente de `0011` vers `0010` ;
3. remontée de `0010` vers `0011` ;
4. suppression de la branche de test.

Résultat : réussi. Aucune base durable n'a été modifiée.

## Architecture

La source Mermaid a été validée par Mermaid CLI 11.12.0 et exportée en SVG. Le rendu a été
inspecté : les trois plans — acquisition, contrôle et contenu — ainsi que la sortie Business
API/MCP sont lisibles et non chevauchants.

## Monorepo

ESLint, TypeScript et Vitest passent (13 tests frontend). Le contrôle Prettier global reste rouge
sur 130 fichiers préexistants hors de cette fonctionnalité. Les nouveaux documents Markdown de
la fondation Data ont été formatés séparément. La machine locale signale aussi Node 22 alors que
le dépôt exige Node 24 ; la CI utilise Node 24.
