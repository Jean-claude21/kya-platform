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
