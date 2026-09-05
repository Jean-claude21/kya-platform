# T077–T078 — Sauvegarde et reprise

Date de contrôle : 2026-09-05

## T077 — Automatisation terminée

La fondation dispose désormais d'un bundle `.kyabackup` :

- trois composants obligatoires : dump Neon, export du store OpenFGA et métadonnées Infisical ;
- chiffrement authentifié AES-256-GCM avec clé externe au bundle ;
- manifeste contenant composant, nom, taille et SHA-256 ;
- refus des doublons, composants manquants, chemins ambigus et cibles de restauration non vides ;
- détection d'une modification du ciphertext ou d'un digest ;
- interdiction des champs `secretValue` et `secret_value` dans l'export Infisical ;
- commandes reproductibles `create`, `verify` et `restore` ;
- documentation des collecteurs officiels `pg_dump`, `fga store export` et API Infisical.

L'export réel des métadonnées du projet Infisical KYA a été exécuté avec
`viewSecretValue=false`, sans référence développée ni override personnel. Les seuls champs liés aux
secrets conservés sont des métadonnées telles que clé, identifiant, chemin, version et indicateurs ;
aucun champ de valeur n'est présent.

## Exercice isolé exécuté

Le script `infra/backup/format_drill.py` a créé, authentifié, ouvert et restauré les trois composants
dans un répertoire temporaire vide. Les tests automatisés ont aussi démontré :

- restauration complète de trois composants ;
- refus d'un bundle modifié ;
- refus d'une valeur secrète Infisical ;
- refus d'écraser une cible existante ;
- refus du même jeton MCP après déprovisionnement KYA.

## T078 — Ce qui reste pour une preuve de reprise fournisseur

T078 reste ouverte. Le drill de format ne prétend pas restaurer les fournisseurs réels. La preuve
complète exige encore :

1. une URL Neon directe de restauration isolée pour `pg_restore` ;
2. une instance et un store OpenFGA de reprise pour `fga store import` ;
3. comparaison des lignes, tuples, modèle actif et décisions d'accès après restauration ;
4. destruction contrôlée des ressources de reprise après conservation des preuves.

Ce périmètre est volontaire : Infisical sauvegarde ici les métadonnées et la structure, jamais les
valeurs secrètes. Les valeurs sont récupérées par rotation ou procédure d'urgence propre à leur
fournisseur.

## Résultats automatisés

```text
Drill de format : 3 composants vérifiés et restaurés
Tests ciblés sauvegarde + révocation : 6 réussis
Backend complet : 215 tests réussis
Couverture : 90,83 % (seuil 90 %)
Ruff : réussi
Mypy : réussi sur 76 fichiers source
```
