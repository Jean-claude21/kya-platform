# Spécification — Connecteur Web institutionnel KYA v0.1

## Résultat attendu

Une ingestion déclenchée par KYA Platform capture le site institutionnel KYA de façon
déterministe, bornée et traçable. Le résultat est un paquet JSON canonique immuable dans le
stockage objet, puis un snapshot Data avec qualité et lignée. L'IA consomme ensuite cette preuve
gouvernée ; elle ne pilote ni le navigateur ni la collecte.

## Premier cas réel

- source détenue par KYA : `https://kya-energy.com/fr` ;
- découverte par sitemap, avec URL de départ de secours ;
- même origine uniquement, HTTPS uniquement ;
- `robots.txt` respecté et identité du collecteur explicite ;
- limites strictes de pages, redirections, taille et délai ;
- plafond global du paquet et contenu toujours marqué non fiable pour les consommateurs IA ;
- HTML brut et champs structurés conservés dans le même paquet probant.

## Contrat du paquet

Chaque page contient l'URL finale, l'heure d'observation, le statut HTTP, le type de contenu,
le digest SHA-256 du corps, le HTML brut, le titre, la langue, les titres, le texte principal,
la canonique et les liens internes. Le paquet est sérialisé avec des clés triées et sans secret.

## Sécurité et fiabilité

- aucun hôte arbitraire fourni au moment du déclenchement ;
- redirections revérifiées avant chaque requête ;
- identifiants, URL avec credentials, IP littérales et ports non standards refusés ;
- écriture objet adressée par digest, donc sûre à rejouer ;
- échec fermé si stockage ou contexte Data manque ;
- le worker termine le run seulement après écriture durable du contenu ;
- les erreurs transitoires sont reprises par le worker à bail existant.

## Hors périmètre v0.1

- rendu JavaScript par navigateur ;
- contournement de CAPTCHA, authentification ou anti-bot ;
- crawl de domaines tiers ;
- classification sémantique par modèle IA ;
- moteur universel de scraping.

## Critères d'acceptation

- une fixture réaliste produit un paquet canonique stable et un digest reproductible ;
- une URL externe, non HTTPS ou trop volumineuse est refusée ;
- robots, limites et redirections sont testés ;
- l'exécution crée un objet immuable et complète le run avec résultats qualité ;
- Ruff, mypy, pytest et contrôles CI passent.
