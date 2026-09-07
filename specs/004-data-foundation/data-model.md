# Modèle de données

| Objet            | Responsabilité                         | Identité stable       |
| ---------------- | -------------------------------------- | --------------------- |
| Source           | Système ou canal d'acquisition         | `source.key`          |
| Actif            | Ensemble de données gouverné           | `asset.key`           |
| Contrat          | Schéma, qualité et SLA immuables       | actif + SemVer        |
| Pipeline         | Liaison source → connecteur → actif    | `pipeline.key`        |
| Exécution        | Tentative observable d'un pipeline     | UUIDv7                |
| Snapshot         | Version matérielle immuable d'un actif | UUIDv7 + SHA-256      |
| Lignée           | Dépendance exacte entre snapshots      | run + entrée + sortie |
| Résultat qualité | Preuve d'évaluation d'une règle        | snapshot + règle      |

Un actif ne possède pas une source unique. Plusieurs pipelines peuvent l'alimenter dans le
temps, et un pipeline de transformation peut consommer plusieurs snapshots. Cette séparation
évite d'enfermer KYA dans Frappe, un site ou un fournisseur de stockage.
