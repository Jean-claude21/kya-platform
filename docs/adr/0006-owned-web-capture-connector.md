# ADR 0006 — Premier connecteur : capture du Web détenu par KYA

## Décision

Le premier connecteur réel capture le site institutionnel KYA. Il s'exécute dans un worker
séparé, sur événement outbox, et produit un paquet JSON canonique dans un stockage S3 compatible.
Neon Object Storage est le fournisseur initial prévu ; le domaine ne dépend pas de Neon.

## Raisons

- source utile, publique et contrôlée par KYA ;
- validation réelle du chemin MCP → Data → outbox → collecte → stockage → snapshot ;
- base réutilisable pour contrôle éditorial, SEO, connaissance produits et détection de changements ;
- risque moindre qu'un premier pilote sur une plateforme tierce ;
- logiciel déterministe pour la collecte, IA pour l'analyse ultérieure.

## Conséquences

- les sources Data possèdent une configuration publique JSON ; les secrets restent référencés ;
- chaque run épingle sa configuration, son actif et son contrat dans l'événement ;
- la collecte est HTTPS, même origine, bornée, attentive à `robots.txt` et sans navigateur ;
- les contenus non HTML et erreurs secondaires deviennent des avertissements qualité ;
- l'activation nécessite des credentials S3 de Neon Storage dans Infisical.

Un futur connecteur de marchés publics réutilisera le protocole Data et le port de stockage, mais
gardera sa propre logique de source, ses règles de conformité et son contrat métier.
