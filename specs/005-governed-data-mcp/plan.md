# Plan d'implémentation — MCP Data gouverné

## Décisions

1. Étendre le serveur MCP Registry existant afin de conserver une connexion KYA unique.
2. Garder OAuth comme consentement grossier et OpenFGA comme décision métier par unité.
3. Réutiliser `DataService` par un adaptateur tardif installé au démarrage FastAPI.
4. Enregistrer l'audit MCP dans la piste append-only déjà disponible.
5. Renvoyer des projections dédiées à l'IA et non les modèles de stockage.
6. Créer une ingestion durable, mais laisser son exécution au futur worker de connecteur.

## Séquence

1. Enrichir les lectures Data nécessaires au MCP.
2. Définir les contrats stricts et sans secret.
3. Ajouter les portées OAuth `data:read` et `data:ingest`.
4. Enregistrer les six outils sur la passerelle existante.
5. Filtrer leur découverte selon l'unité active et OpenFGA.
6. Corréler les décisions et résultats dans l'audit.
7. Tester contrat, runtime, persistance et scénarios négatifs.
8. Exécuter les validations locales et distantes avant fusion dans `dev`.

## Risque assumé

L'audit d'invocation MCP et l'écriture métier utilisent deux transactions distinctes. L'écriture
`start_ingestion` reste néanmoins traçable atomiquement par son événement outbox Data. Une future
projection d'audit issue de l'outbox pourra unifier la preuve technique et la preuve d'invocation.
