# Plan d'implémentation

1. Définir le contrat de capture et ses invariants de sécurité.
2. Implémenter l'extraction HTML déterministe et la sérialisation canonique.
3. Implémenter un client HTTP borné avec validation de chaque destination.
4. Ajouter le port de stockage immuable et l'adaptateur S3 compatible Neon Storage.
5. Relier capture, stockage et `DataService.complete_run` dans un handler de worker.
6. Tester les cas nominaux, rejoués, hostiles et les limites.
7. Publier le schéma d'exécution et les preuves de validation.

La configuration opérationnelle reste référencée par la source Data et les secrets de stockage
sont injectés depuis Infisical. Neon PostgreSQL demeure le plan de contrôle ; Neon Object Storage
contient les octets. L'adaptateur repose uniquement sur le protocole S3 afin de rester portable.
