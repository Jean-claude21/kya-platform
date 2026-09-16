# Plan — Évaluation automatique des veilles

1. Enrichir le contrat de l'événement de fin d'ingestion.
2. Ajouter un handler déterministe pour les veilles actives.
3. Brancher le handler sur le worker outbox existant.
4. Tester sélection, attribution, idempotence et payload invalide.
5. Déployer puis prouver le flux avec une veille créée par un utilisateur réel.
