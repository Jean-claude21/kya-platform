# Surface brief — Shell KYA Platform

## Scope et mode

Shell applicatif interne, orienté **opérations**. Il doit permettre à un collaborateur de comprendre les capacités accessibles dans son contexte, de les rechercher, de les utiliser et de faire avancer leur cycle de publication.

## Public, tâche et preuve

- Public : collaborateurs KYA, responsables de domaine, validateurs, CVSI et stagiaires.
- Tâche principale : trouver une capacité autorisée et agir sans connaître son implémentation technique.
- Action principale : rechercher ou parcourir le réseau de capacités.
- Preuve : la chaîne Sources → Données → Business API → MCP → Skills → Collaborateurs, les états, environnements, propriétaires et décisions.
- Contraintes : français, faible bande passante, clavier et mobile, autorisations par contexte organisationnel, aucune clé secrète affichée.

## Direction retenue

Un tableau de conduite énergétique lumineux et sobre. Le réseau de capacités est le mécanisme mémorable : il rend visibles les dépendances, les permissions et les états sans transformer l’interface en schéma purement technique. Les décisions à prendre restent adjacentes et actionnables.

Référence approuvée : `.impeccable/mocks/capability-network-b.png`.

## Inventaire de fidélité

| Élément                     | Engagement                                           | Médium                        |
| --------------------------- | ---------------------------------------------------- | ----------------------------- |
| En-tête et commande globale | Contexte organisationnel toujours visible            | HTML/CSS sémantique           |
| Navigation                  | Horizontale sur grand écran, compacte sur mobile     | HTML/CSS + icônes SVG         |
| Réseau de capacités         | Six couches, branches, états et permissions lisibles | SVG réactif + HTML accessible |
| File de décisions           | Trois cartes hiérarchisées avec actions directes     | HTML/CSS                      |
| Recommandations             | Capacités pertinentes selon le rôle actif            | HTML/CSS                      |
| Déploiements                | Version, environnement et état                       | Tableau HTML adaptatif        |
| Action principale           | Recherche/commande globale, disponible au clavier    | HTML natif                    |

## À ne pas littéraliser

Les métriques et noms du mockup sont illustratifs. Le produit réel utilisera des données typées et autorisées. Les lignes du réseau ne doivent pas devenir une animation décorative ; elles servent la navigation et l’explication du système.

## Décisions encore ouvertes

- Logo officiel à intégrer quand l’actif source sera fourni.
- Police institutionnelle à substituer si une charte typographique officielle existe.
