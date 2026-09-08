# Preuves de validation

## Capture réelle — 8 septembre 2026

La capture en lecture seule de `https://kya-energy.com/fr` a produit :

- 3 pages HTML bornées : accueil, à propos, certifications ;
- 579 929 octets dans le paquet canonique ;
- digest `c3c46c3e3fca29564173a3b3f53e4cbba6b5454efb0c49b3f982196ddcc96bdc` ;
- un avertissement explicite pour le PDF de politique qualité, volontairement non traité comme HTML ;
- `robots.txt` et `sitemap.xml` absents avec réponse HTTP 404 ; conformément au protocole robots,
  le connecteur a utilisé l'URL de départ puis les liens internes, sans quitter les hôtes KYA.

Le digest représente cette observation et changera légitimement lorsque le contenu source change.

## Validation automatisée

- Ruff : réussi ;
- mypy strict : réussi sur 119 fichiers source ;
- pytest : 434 tests réussis ;
- couverture : 90,33 % ;
- rendu Mermaid SVG/PNG généré et contrôlé visuellement ;
- stockage testé sur succès, rejeu immuable et collision de digest ;
- worker testé de l'événement jusqu'au snapshot Data.

## Activation restante

Le code est désactivé par défaut. L'essai de stockage réel nécessite l'endpoint, la région, le
bucket, l'access key et la secret key S3 de la branche Neon Object Storage. Ces valeurs doivent
être placées dans Infisical puis injectées au worker ; elles ne sont pas disponibles dans le
`.env` backend au moment de cette validation.
