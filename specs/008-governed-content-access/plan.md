# Plan d'implémentation

1. Projeter chaque page capturée en document et passages déterministes.
2. Persister la projection avec le snapshot, la qualité et la lignée dans une transaction.
3. Indexer les passages avec le plein texte PostgreSQL et un index GIN.
4. Filtrer en profondeur par unité, statut actif et classification publique.
5. Exposer recherche et relecture par des contrats MCP stricts et cités.
6. Ajouter la portée OAuth dédiée et l'audit obligatoire.
7. Valider localement, en CI, puis déployer uniquement sur `dev`.

L'ordre de confiance reste : objet brut immuable → projection reconstructible → autorisation →
outil MCP borné → raisonnement dans le client choisi par l'utilisateur.
