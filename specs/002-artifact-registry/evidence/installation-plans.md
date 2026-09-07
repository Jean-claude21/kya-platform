# Preuve T016 — plans d'installation

## Garanties automatisées

- mêmes entrées immuables, même `plan_id` UUIDv5 ;
- release et version obligatoirement publiées ;
- digest release/version identique ;
- signature Ed25519 vérifiée avec la clé publique de confiance ;
- profil déclaré dans le manifeste et version client compatible ;
- sept actions fermées, sans commande libre ni secret ;
- destinations Codex, Claude Code et zip couvertes ;
- refus des locators locaux/non supportés et des artefacts non-Skill pour les profils agents ;
- appel MCP contrôlé par `catalog:install`, unité active et relation OpenFGA `can_install`.

## Validation attendue

`ruff check`, `mypy` et la suite `pytest` complète doivent réussir avec une couverture globale d'au
moins 90 %. Cette preuve complète T016 ; l'écriture du reçu, la gestion des mises à jour et le
rollback persistant relèvent de T017.
