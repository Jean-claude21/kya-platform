# ADR 0004 — Séparer contrôle, contenu et exécution des données

## Statut

Accepté — 7 septembre 2026.

## Décision

KYA Data Foundation conserve dans Neon PostgreSQL les sources, actifs, contrats, pipelines,
exécutions, preuves qualité et lignée. Les contenus volumineux sont stockés comme objets
immuables ; PostgreSQL ne conserve que leur référence et leur digest.

Les connecteurs sont des artefacts gouvernés du catalogue et chaque pipeline épingle une
version précise. Les identifiants de secrets sont opaques et leur valeur reste dans Infisical.

## Pourquoi

Cette séparation rend les acquisitions rejouables et auditables, évite les interfaces dédiées
à chaque besoin et permet aux applications comme aux environnements IA d'exploiter une même
donnée fiable. Elle autorise aussi une migration progressive hors de Frappe sans migration
brutale des usages existants.

## Conséquences

- le scraping est une famille de connecteurs, pas une route web générique ;
- l'IA ne devient pas responsable des garanties déterministes ;
- toute donnée publiée possède un contrat, une provenance et une preuve de qualité ;
- changer de stockage ou de système source n'altère pas l'identité des actifs.
