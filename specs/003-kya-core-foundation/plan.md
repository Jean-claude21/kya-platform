# Plan d'implémentation — KYA Core v0.1

## Décision d'architecture

KYA Core est un domaine du monolithe modulaire. Les API, MCP futurs et adaptateurs dépendent de ses
ports applicatifs. KYA Core ne dépend d'aucun système externe. Neon est son stockage autoritaire ;
OpenFGA reste l'autorité d'accès ; l'outbox existante transporte les événements.

## Tranche 1

1. Consolider les objets de valeur et agrégats du domaine.
2. Créer le schéma `core` et ses contraintes.
3. Implémenter un dépôt transactionnel SQLAlchemy.
4. Exposer les commandes et lectures minimales par `/api/v1/core`.
5. Réutiliser et vérifier les relations `org_unit.can_view` et `org_unit.can_manage` du modèle OpenFGA.
6. Valider domaines, contrats, migrations, sécurité et non-régression.

## Frontières

```text
API / futur MCP / futur adaptateur
              │
              ▼
       Application KYA Core
       ├── autorisation
       ├── orchestration
       └── ports
              │
       ┌──────┴──────┐
       ▼             ▼
   Domaine       Dépôt Neon
  déterministe   + audit/outbox
```

## Choix structurants

- `Party` sépare les personnes réelles et organisations des comptes d'authentification.
- `WorkRelationship` porte le caractère collaborateur/stagiaire et sa période.
- Les dates restent en deux colonnes explicites dans le modèle applicatif ; PostgreSQL construit
  des `tstzrange` dans les contraintes d'exclusion lorsque l'unicité temporelle l'exige.
- Les suppressions physiques ne sont pas exposées ; les changements de statut préservent les références.
- Les ressources sont adressées par UUID dans les contrats et peuvent offrir une clé lisible unique.
- Les listes de la tranche 1 sont limitées au périmètre propriétaire exact. L'héritage des droits
  est décidé par OpenFGA ; l'élargissement aux descendants fera l'objet d'un contrat explicite.
- L'unité racine `group` est une donnée de référence déterministe créée par migration. Son auteur
  technique est le principal système réservé `01993450-0000-7000-8000-000000000000` ; le premier
  propriétaire humain reste établi séparément par le bootstrap sécurisé existant.

## Conformité à la constitution

| Porte                        | Décision                                             |
| ---------------------------- | ---------------------------------------------------- |
| Spécification et traçabilité | PASS — dossier Spec Kit 003                          |
| Modularité et autorités      | PASS — domaine sans dépendance Frappe                |
| Moindre privilège            | PASS — garde OpenFGA sur l'unité de périmètre        |
| IA / déterminisme            | PASS — invariants et mutations exécutés par logiciel |
| Qualité et réversibilité     | PASS — migration réversible, tests et outbox         |
