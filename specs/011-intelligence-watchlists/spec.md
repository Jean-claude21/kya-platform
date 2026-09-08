# Spécification — Veilles gouvernées KYA Intelligence v0.1

**Branche** : `feat-intelligence-watchlists`  
**Date** : 2026-09-08  
**Statut** : prêt pour implémentation

## Intention

Transformer les données déjà acquises par KYA-Platform en signaux métier partagés, sans intégrer un
modèle d'IA imposé. Le logiciel détecte de façon déterministe les nouveaux contenus correspondant à
une veille ; Claude, ChatGPT ou un autre environnement autorisé raisonnent ensuite sur des preuves
citables via MCP.

## Scénarios utilisateurs

### US1 — Créer une veille gouvernée (P1)

Un collaborateur autorisé crée une veille dans son unité active avec un nom, une requête et, si
nécessaire, une liste bornée d'actifs de données. La commande est idempotente et l'auteur reste
identifiable.

### US2 — Détecter les nouveaux signaux (P1)

Le système évalue une veille sur les contenus gouvernés visibles. Chaque fragment correspondant
devient au plus un signal pour cette veille, avec citation, source, date d'observation et empreintes.
Une nouvelle évaluation ne duplique jamais les signaux déjà vus.

### US3 — Consulter et acquitter (P1)

Un utilisateur autorisé liste les signaux ouverts et peut les acquitter. L'acquittement est audité ;
la preuve d'origine reste immuable.

### US4 — Exploiter la veille depuis un environnement IA (P2)

Claude ou ChatGPT peut créer une veille, lancer une évaluation, lister les signaux et citer leurs
sources via les outils MCP du profil autorisé. Une écriture exige confirmation et idempotence.

## Règles

- Une veille appartient exactement à une unité organisationnelle et à un créateur.
- La requête contient de 2 à 200 caractères ; une veille cible au plus 50 actifs explicites.
- Seuls les contenus déjà filtrés par la couche d'accès gouvernée peuvent produire des signaux.
- Un signal contient une preuve, jamais une conclusion générée par IA présentée comme un fait.
- L'unicité `(veille, fragment)` rend l'évaluation rejouable et concurrente sans doublon.
- Une veille mise en pause ne peut pas être évaluée ; ses signaux restent lisibles.
- L'API et MCP utilisent le même service applicatif et les mêmes autorisations serveur.

## Exigences fonctionnelles

- **FR-001** — Créer une veille atomiquement et de façon idempotente.
- **FR-002** — Lister les veilles de l'unité active sans fuite inter-unités.
- **FR-003** — Évaluer une veille active à partir de la recherche de contenus gouvernée.
- **FR-004** — Dédupliquer les signaux par veille et fragment de contenu.
- **FR-005** — Conserver citation, URI source, extrait, empreintes et date d'observation.
- **FR-006** — Acquitter un signal avec auteur, date et révision optimiste.
- **FR-007** — Émettre audit et outbox pour les mutations.
- **FR-008** — Exposer des outils MCP profilables avec refus par défaut.
- **FR-009** — Ne stocker ni prompt privé, ni jeton, ni sortie de modèle comme preuve factuelle.

## Critères de réussite

- **SC-001** — Deux évaluations identiques créent zéro doublon.
- **SC-002** — Chaque signal retourné possède une citation et une URI source.
- **SC-003** — Une veille d'une autre unité n'est ni listée ni évaluable.
- **SC-004** — Une panne d'autorisation ou de base ne crée aucun état partiel.
- **SC-005** — Une évaluation pilote de 50 résultats répond en moins de 2 secondes hors collecte.

## Hors périmètre v0.1

- génération automatique de rapports par un modèle hébergé par KYA ;
- scraping ou ingestion dans ce module ;
- notifications e-mail/Teams ;
- recherche vectorielle ou classement personnalisé ;
- tableau de bord analytique avancé.

