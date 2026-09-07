# Spécification — KYA Data Foundation v0.1

## Résultat attendu

KYA peut enregistrer une source, déclarer un actif de données et son contrat, rattacher un
connecteur publié, tracer chaque acquisition et référencer un snapshot immuable. La même
donnée devient réutilisable par la Business API, les applications et, ensuite, les MCP.

## Principes non négociables

- La source métier, le connecteur exécutable et l'actif de données sont trois objets distincts.
- Un pipeline épingle une version publiée de connecteur ; une mise à jour n'altère pas l'historique.
- Les secrets restent dans Infisical. La base ne conserve qu'une référence opaque.
- Les octets restent dans le stockage objet. Neon PostgreSQL conserve les métadonnées gouvernées.
- Un snapshot est immuable, adressé par digest et lié au contrat utilisé.
- La lignée relie des snapshots précis, pas seulement des noms de tables.
- Toute lecture et écriture reste limitée à une unité KYA explicitement autorisée.
- La collecte déterministe précède le raisonnement IA : l'IA interprète, le logiciel acquiert,
  valide, journalise et rejoue.

## Scénario vertical v0.1

1. Le CVSI enregistre une source web, API, base, fichier, flux ou saisie manuelle.
2. Il déclare un actif `raw`, `standardized`, `curated` ou `product`.
3. Il publie un contrat SemVer contenant schéma, règles de qualité, fraîcheur et rétention.
4. Il crée un pipeline qui épingle une version de connecteur du catalogue.
5. Un acteur ou un ordonnanceur démarre une exécution.
6. Le connecteur écrit le contenu dans le stockage objet.
7. La plateforme termine l'exécution avec le snapshot, les résultats qualité et la lignée.
8. Les consommateurs interrogent les métadonnées ; aucune URL signée n'est persistée.

## Hors périmètre v0.1

- moteur universel de scraping ;
- orchestration distribuée et planification avancée ;
- transformation SQL/ELT ;
- interface BI ;
- adaptateur Frappe ;
- exposition MCP des données.

Ces éléments s'ajouteront comme capacités sans modifier les identités stables de cette fondation.

## Critères d'acceptation

- Les invariants du domaine et de PostgreSQL rejettent les états incohérents.
- Une exécution terminale ne peut revenir à l'état démarré.
- Un pipeline refuse une source, un actif ou un connecteur hors référentiel.
- La version de connecteur ciblée est publiée et de type `connector`.
- Le contrat d'un snapshot appartient à son actif.
- Les snapshots d'entrée et de sortie de la lignée existent et sont distincts.
- Les mutations sont idempotentes, transactionnelles et émettent un événement outbox.
- La migration monte, redescend puis remonte sur une branche Neon éphémère.
