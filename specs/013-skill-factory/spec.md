# Spécification — Fabrique de Skills KYA

## Objectif

Permettre aux Directions et au CVSI de créer rapidement des Skills complets, portables,
versionnés et publiables dans KYA-Platform, sans réduire un Skill à du texte simple.

## Structure cible

Chaque Skill contient `SKILL.md`, son manifeste KYA et, uniquement selon son besoin, des
métadonnées d'agent, références, assets, templates, schémas, scripts et tests. Tout code exige un
manifeste de capacité, une SBOM et des tests.

## Capacités v0.1

- initialiser une arborescence déclarative minimale et valide ;
- assembler un ZIP reproductible avec inventaire et digests recalculés ;
- valider le ZIP sans extraire ni exécuter son contenu ;
- refuser écrasement, chemins hors contrat, secrets probables et code non déclaré ;
- produire le même paquet pour un même contenu ;
- rester compatible avec l'import, la publication et la distribution déjà présents dans le
  registre KYA.

## Hors périmètre

- générer le savoir métier à la place de la Direction propriétaire ;
- exécuter les scripts dans le registre ;
- publier sans preuves ni approbation ;
- installer silencieusement sur le poste d'un collaborateur.

## Critères d'acceptation

1. Un auteur initialise un Skill en une commande.
2. Le paquet produit passe le validateur du registre.
3. Deux assemblages du même contenu sont identiques octet par octet.
4. Un Skill avec script incomplet est refusé fermé.
