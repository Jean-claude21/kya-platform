# Preuve T015 — Publication gouvernée persistante

## Résultat

La publication ne repose plus sur un état mémoire. Neon conserve le candidat figé, les preuves,
les décisions humaines et la release signée. Les événements d'audit asynchrones sont inscrits dans
l'outbox au sein de la même transaction.

## Contrôles bloquants

- version candidate déjà persistée et commit/digests strictement identiques ;
- attestations uniques, immuables, réussies, non expirées et liées au digest du candidat ;
- socle minimal de cinq preuves, renforcé à neuf pour le code ou les actions mutatives ;
- auteur, relecteur et approbateur distincts ;
- release Ed25519 unique avec champs d'intégrité immuables ;
- endpoints soumis aux relations OpenFGA `can_submit`, `can_review` et `can_approve` ;
- clé privée fournie uniquement par variable secrète et jamais stockée en base.

## Validation locale

- Ruff : réussi ;
- mypy strict : réussi ;
- pytest : 324 tests réussis ;
- couverture backend : au moins 90 %.

La migration `20260907_0008` crée `catalog.attestation`, `catalog.publication_request` et
`catalog.release`, ainsi que le verrou PostgreSQL empêchant toute mutation des champs d'intégrité
d'une release publiée.
