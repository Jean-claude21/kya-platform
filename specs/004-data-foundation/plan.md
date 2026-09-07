# Plan d'implémentation

## Tranche 1 — Modèle et persistance

- domaine indépendant des fournisseurs ;
- schéma PostgreSQL `data` ;
- migration réversible ;
- contrats, qualité et lignée au niveau snapshot.

## Tranche 2 — Business API

- gestion des sources, actifs, contrats et pipelines ;
- cycle démarrer / terminer / échouer d'une exécution ;
- consultation des snapshots et de leur provenance ;
- autorisation par unité, idempotence et outbox.

## Tranche 3 — Premier connecteur réel

Le premier cas sera choisi après validation de la fondation. Un connecteur spécialisé pourra
faire du scraping robuste, appeler une API ou lire Frappe. Il produira tous le même protocole
d'exécution et de snapshot.

## Décision de stockage

Neon PostgreSQL est le plan de contrôle. Neon Object Storage est le premier fournisseur de
contenu prévu, derrière le type neutre `StorageObject`. Une référence contient fournisseur,
conteneur, clé d'objet et version ; jamais un secret ni une URL temporaire.
