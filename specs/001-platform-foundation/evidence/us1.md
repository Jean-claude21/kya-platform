# Preuves US1 — Espaces et accès

**Date d'exécution** : 2026-09-04  
**Branche** : `feat-platform-foundation`

## Périmètre démontré

- Organisation configurable : types d'unités, unités, relations hiérarchiques et transversales.
- Historisation par périodes semi-ouvertes (`valid_from` inclus, `valid_until` exclu).
- Postes et affectations multiples, principales, secondaires, intérimaires ou déléguées.
- Espaces reliés à une ou plusieurs unités, sans déduire les permissions d'un intitulé de poste.
- Accès direct ou hérité, contexte organisationnel actif obligatoire et interdiction explicite
  prioritaire.
- Liste des espaces filtrée par le moteur d'autorisation avant tout chargement métier.
- Explication stable d'une décision sans copie des valeurs sensibles du contexte.

## Matrice de référence

| Persona | Situation vérifiée                             | Résultat                                                                        |
| ------- | ---------------------------------------------- | ------------------------------------------------------------------------------- |
| Alice   | Administratrice Groupe, contexte CVSI actif    | Consultation, modification et gestion autorisées                                |
| Alice   | Même responsabilité sans contexte actif        | Consultation et gestion refusées                                                |
| Bob     | Membre de l'équipe Développeurs                | Consultation, modification et invocation MCP autorisées ; gestion refusée       |
| Bob     | Interdiction explicite sur l'espace et l'outil | Tous les droits concernés refusés malgré l'héritage                             |
| Chloé   | Délégation de publication au 15 septembre 2026 | Soumission et revue autorisées ; approbation refusée                            |
| Chloé   | Même délégation au 1er octobre 2026            | Soumission automatiquement refusée après expiration                             |
| Sam     | Stagiaire membre de l'espace                   | Lecture et découverte autorisées ; écriture, gestion et invocation MCP refusées |

## Résultats reproductibles

### Politique OpenFGA

Commande officielle exécutée avec l'image CLI épinglée par digest :

```text
docker run --rm --volume "${PWD}:/work" --workdir /work \
  openfga/cli:v0.7.15@sha256:889801086b7b5d5239b9a2210e03e75ed8ff141bdfbe0238894bcb06d02d6780 \
  model test --tests tests/policy/kya-platform.fga.yaml
```

Résultat : **9/9 scénarios et 31/31 contrôles réussis**.

### Backend

Résultat : **91 tests réussis**, couverture totale **91,55 %**, seuil requis **90 %**.

Les tests d'intégration prouvent notamment :

- refus d'un accès direct sans divulgation du nom ni du contenu de l'espace ;
- liste vide lorsque le contexte actif ne correspond pas ;
- chargement exclusif des clés déjà autorisées ;
- refus de modifier les membres sans `can_manage` ;
- création d'une affectation datée par un gestionnaire autorisé.

### Interface

- TypeScript strict : réussi.
- Build Vite client et SSR : réussi.
- Tests de composant : **2/2 réussis**.
- Actions d'écriture non encore reliées à Neon explicitement désactivées et marquées « bientôt ».
- Les données affichées dans la vue sont identifiées comme données de démonstration.

## Limite constatée

La capture visuelle locale ordinateur/mobile n'a pas pu être exécutée le 4 septembre 2026 : la
vue du navigateur intégré n'a pas réussi à s'attacher au serveur local après deux tentatives. Le
build, les tests de composant et les contrôles statiques sont concluants, mais la revue visuelle
reste à refaire avant promotion vers `dev`.
