# Spécification — Évaluation automatique des veilles

## Objectif

Après chaque ingestion gouvernée réussie, évaluer automatiquement les veilles actives de
l'unité concernée et matérialiser des signaux citables, sans modèle d'IA ni action manuelle.

## Règles

- l'événement `kya.data.run.completed.v1` transporte l'unité, le snapshot et l'actif concernés ;
- seules les veilles actives de cette unité sont évaluées ;
- l'acteur et la corrélation de l'ingestion sont conservés dans les preuves ;
- la commande est idempotente par couple run/veille ;
- une veille en pause est ignorée ;
- une erreur est retentée par le mécanisme de lease existant, puis mise en dead-letter ;
- le déclenchement manuel reste disponible pour les reprises et diagnostics.

## Hors périmètre

- interprétation par un LLM ;
- notifications ;
- planification de prompts Claude/ChatGPT ;
- recherche vectorielle.

## Critères d'acceptation

1. Une ingestion terminée déclenche l'évaluation sans intervention humaine.
2. Rejouer l'événement ne duplique aucun signal ni effet métier.
3. Les frontières d'unité sont préservées.
4. Le worker de collecte ne consomme que ses deux topics explicitement autorisés.
