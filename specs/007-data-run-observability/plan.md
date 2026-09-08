# Plan d'implémentation

1. Ajouter au service Data une vue agrégée `IngestionRunReport`.
2. Charger cette vue dans le dépôt Neon avec filtrage par unité active.
3. Définir les contrats MCP stricts et secret-safe.
4. Enregistrer `get_ingestion_run` dans la passerelle gouvernée.
5. Couvrir la persistance, l'autorisation, l'audit et la non-divulgation.
6. Valider localement, en CI puis déployer sur l'environnement `dev`.

La couche MCP ne lit jamais SQL directement. Elle passe par `DataService`, comme l'API et le
worker, afin que les invariants restent identiques sur tous les canaux.
