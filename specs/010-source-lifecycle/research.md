# Recherche ciblée — Cycle de vie des sources

## Décisions

1. **Agrégat transactionnel local** : les objets Data existants partagent PostgreSQL ; une transaction
   unique garantit l'absence d'état partiel sans ajouter de saga prématurée.
2. **Intervalle borné en v0.1** : il couvre les collectes opérationnelles KYA et évite un moteur Cron
   arbitraire avant d'avoir des besoins factuels.
3. **Ordonnanceur serveur** : l'acquisition ne dépend pas de la disponibilité d'un agent IA.
4. **Verrouillage de ligne et idempotence** : `FOR UPDATE SKIP LOCKED` permet plusieurs workers sans
   double déclenchement.
5. **Pas de suppression** : pause et retraite préservent preuves, citations et lineage.
6. **Connecteur résolu par identité publique** : l'API ne demande pas aux utilisateurs de connaître
   des UUID internes de versions.
