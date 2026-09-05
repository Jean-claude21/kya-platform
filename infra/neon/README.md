# Neon — previews isolées

Chaque preview doit utiliser une branche Neon éphémère dérivée de `dev`, avec des données
non productives. Le nom recommandé est `preview/<pull-request-number>`. La branche est
supprimée après fermeture de la PR. Les migrations sont exécutées avant les tests et leur
identifiant est conservé dans l’artefact de build.

Le workflow attend `NEON_API_KEY` et `NEON_PROJECT_ID` dans le gestionnaire de secrets.
`NEON_PROJECT_ID` désigne le conteneur technique Neon (un compte/projet PostgreSQL).
Il ne représente ni une Direction, ni une équipe, ni un espace KYA. Les espaces et droits
restent multi-périmètres et sont évalués par KYA Platform/OpenFGA.
Le backend reçoit uniquement une `KYA_DATABASE_URL` de preview ; aucune URL de production
ne doit être exposée aux jobs de pull request.
