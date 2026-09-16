# Tâches — KYA Core v0.1

- [x] T001 Définir périmètre, scénarios, modèle et contrats.
- [x] T002 Consolider le domaine parties, relations de travail, clients, projets et sites.
- [x] T003 Ajouter les modèles SQLAlchemy du schéma `core`.
- [x] T004 Ajouter la migration Alembic et les contraintes temporelles.
- [x] T005 Ajouter les ports et le dépôt transactionnel avec outbox.
- [x] T006 Ajouter la garde d'autorisation par unité active.
- [x] T007 Exposer la tranche Business API minimale.
- [x] T008 Vérifier la compatibilité avec les relations d'unité du modèle OpenFGA existant.
- [x] T009 Ajouter tests unitaires, contrats, intégration et migration.
- [x] T010 Exécuter formatage, lint, mypy et suite complète.
- [x] T011 Documenter les preuves et limites de la tranche.

## Preuves du 7 septembre 2026

- `ruff check` : réussi ;
- `mypy` : 102 fichiers source, aucune erreur ;
- `pytest` : 382 tests réussis, couverture globale 90,28 % ;
- Alembic : construction complète jusqu'à `20260907_0010`, retour à `20260907_0009`,
  puis rejeu réussi sur une branche Neon éphémère et supprimée ;
- Neon : schéma `core`, dix types d'unités et racine active `KYA-Energy Group` vérifiés.
