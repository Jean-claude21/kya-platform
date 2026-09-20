# Spécification — Fondation des applications KYA

## Résultat attendu

Une application autonome peut être déclarée, publiée, découverte et ouverte depuis KYA-Platform
sans dupliquer l'identité, l'organisation, les permissions, le catalogue, les secrets ou l'audit.
Le même contrat reste utilisable par les Skills, MCP, API et produits de données.

## Frontières

- KYA-Platform est le plan de contrôle : identité, contexte, autorisation, registre et audit.
- Une application possède son dépôt, ses données métier et son déploiement.
- Le SDK transmet le jeton et le contexte actif ; OpenFGA reste la frontière de confiance.
- Le manifeste ne contient aucune valeur secrète.
- Une URL de lancement n'est exposée qu'après filtrage des droits et résolution d'une version publiée.

## Contrat universel

Le manifeste commun conserve l'identité immuable de la version et peut déclarer :

- gouvernance : visibilité, portée par défaut, portées autorisées et permissions communes ;
- fonctionnalités : clé stable et permissions nécessaires ;
- application : URL, mode de lancement, icône, santé et version SDK attendue ;
- intégrations : API, événements, webhooks et outils MCP, sans identifiants secrets.

Les états de cycle de vie restent des métadonnées mutables du registre. Ils ne sont pas copiés dans
le manifeste signé de chaque version.

## Permissions communes

`view`, `use`, `create`, `edit`, `administer`, `publish`, `share` sont les verbes publics. Leur
résolution reste effectuée côté serveur à partir des relations OpenFGA existantes. Une application ne
peut pas s'accorder elle-même une permission en la déclarant dans son manifeste.

## Événements

Les applications produisent une enveloppe versionnée, corrélée et rattachée au contexte KYA. Les
webhooks utilisent une signature HMAC SHA-256 horodatée. Le secret de signature est résolu au moment
de la livraison depuis Infisical et n'entre jamais dans le catalogue.

## Données métier

Le contrat `record-schema/v1` décrit les champs, choix, relations, pièces jointes, versions,
rétention et permissions au niveau du schéma ou de l'enregistrement. Il est commun à Forms,
Workflow et aux futures applications ; chaque produit conserve son moteur d'exécution et ses
données. Une pièce jointe est régie par une politique de taille et de type, jamais par une URL
signée persistée dans le schéma.

## Critères d'acceptation

- Un ancien manifeste reste valide sans les nouvelles déclarations optionnelles.
- Un artefact non `app` ne peut pas déclarer de métadonnées de lancement.
- Le registre d'applications ne renvoie que les artefacts autorisés, publiés et disposant d'une
  release publiée.
- Les permissions effectives sont calculées par le serveur et non par le navigateur.
- Le SDK expose session, contextes Core, registre d'applications, erreurs structurées et télémétrie
  sans jeton.
- Le shell présente les états chargement, vide, erreur, restreint et disponible.
- Les contrats JSON Schema et les templates officiels sont testés en CI.
