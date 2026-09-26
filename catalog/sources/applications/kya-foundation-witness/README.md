# Application témoin de recette

Cette application technique est séparée de KYA Core et ne contient aucune donnée ou règle métier.
Elle expose seulement `GET /` pour vérifier le lancement et `GET /health` pour vérifier la santé.

Déployer le contenu autonome de `tools/recette-app/Dockerfile` comme application Dockerfile sans
Git sur une cible Coolify de recette. Utiliser son URL publique
comme `launch_url` et ajouter `/health` comme `health_url` dans l'enregistrement de l'application
publiée. La publication de l'artefact, l'enregistrement et l'affectation s'effectuent via les contrats
gouvernés de la plateforme ; aucune ligne SQL n'est créée par ce service.

Ce serveur n'authentifie pas le visiteur. La recette de visibilité et de lancement se fait avec deux
comptes Auth dans KYA-Platform ; la recette des API/SDK sous identité applicative se fait avec
`tools/application-owner-recipe.mjs`. Une visite directe de l'URL ne prouve aucun droit.

## Proposition gouvernée

Depuis la racine : `uv run --project apps/backend python tools/recette-app/build_proposal.py`.
Le paquet généré contient quatre fichiers et passe le validateur des propositions applicatives.
Le manifeste est une proposition : sa provenance Git et son empreinte seront produites par le
serveur après revue et fusion vérifiée. La commande ne publie rien et ne crée aucune ligne SQL.
Soumettre ce paquet dans l'espace `platform` avec le contrat `/proposals`, puis utiliser une
autre personne habilitée pour la revue, ou la dérogation administrateur explicite et auditée
déjà prévue par la plateforme. La décision du 26 septembre autorise cette dérogation ;
`techteam@kya-energy.com` reste le compte prévu pour la recette à deux identités.

Le client `submit.html`/`submit.js` peut être servi par le Vite local en mode `recette`, sous
`/@fs/<chemin-absolu-du-dépôt>/tools/recette-app/submit.html`. Il réutilise le client Auth Web
pour appeler l'API sans afficher ni copier le jeton. Il n'entre pas dans le build Web du socle.
