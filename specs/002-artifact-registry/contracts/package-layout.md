# Contrat de paquet KYA v1

```text
artifact-root/
├── artifact.manifest.json       obligatoire
├── capability.manifest.json     si contenu exécutable
├── SKILL.md                     obligatoire pour type skill
├── scripts/                     optionnel, classifié exécutable
├── references/                  optionnel
├── templates/                   optionnel
├── schemas/                     optionnel
├── examples/                    optionnel
├── tests/                       requis selon le risque
└── assets/                      optionnel
```

Le manifeste publié contient ou référence l'inventaire canonique. Les noms sont sensibles à la
casse mais deux chemins ne peuvent différer uniquement par la casse. Les liens symboliques, devices,
sockets, chemins absolus et segments `..` sont interdits dans le profil portable initial.

## Classification

- `instruction`: Markdown lu par l'agent.
- `reference`: connaissance factuelle chargée à la demande.
- `template`: document ou squelette copié sans exécution.
- `schema`: contrat validable.
- `script`: code potentiellement exécutable.
- `test`: contrôle déterministe.
- `asset`: ressource binaire non exécutable.

Un paquet comportant `script`, macro, binaire natif ou commande reçoit
`hasExecutableContent=true` et exige `capability.manifest.json`, analyse de dépendances, SBOM,
tests en sandbox et approbation technique.

## Intégrité et ingestion

- L'import initial accepte une archive ZIP portable et bornée ; son contenu n'est jamais extrait
  sur le serveur et aucun fichier n'est exécuté.
- `artifact.integrity.digest` est le SHA-256 de l'inventaire canonique des contenus, hors
  `artifact.manifest.json` afin d'éviter une référence circulaire. Chaque entrée contient le
  chemin, la taille et le SHA-256 du fichier.
- Le registre recalcule les digests depuis les octets reçus. Il ne fait pas confiance aux valeurs
  déclarées par le client.
- Les liens symboliques, entrées chiffrées, taux de compression suspects, binaires natifs,
  secrets probables et chemins ambigus sont refusés avant toute persistance.
- Un Skill exécutable exige un manifeste de capacité, au moins un test et une SBOM CycloneDX.
