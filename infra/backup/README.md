# Sauvegarde de la fondation

Le bundle `.kyabackup` regroupe trois exports obligatoires, chiffrés et authentifiés en
AES-256-GCM : Neon, OpenFGA et les métadonnées Infisical. La clé est une valeur base64 représentant
exactement 32 octets dans `KYA_BACKUP_ENCRYPTION_KEY`. Elle doit rester dans Infisical, séparée des
bundles.

## Collecte

Utiliser une URL Neon directe, jamais l'URL poolée :

```shell
pg_dump -Fc --no-owner --no-privileges --file neon.dump "$KYA_DATABASE_MIGRATION_URL"
```

Exporter le store OpenFGA complet avec le CLI officiel :

```shell
fga store export --store-id "$FGA_STORE_ID" > openfga.fga.yaml
```

Exporter uniquement les métadonnées Infisical. Le script envoie `viewSecretValue=false`, refuse
les références développées et supprime encore défensivement tout champ `secretValue` reçu :

```shell
uv run --package kya-platform-backend python infra/backup/infisical_metadata.py infisical-metadata.json
```

## Création et vérification

```shell
uv run --package kya-platform-backend python infra/backup/foundation_backup.py create \
  --neon neon.dump \
  --openfga openfga.fga.yaml \
  --infisical-metadata infisical-metadata.json \
  --output kya-foundation.kyabackup

uv run --package kya-platform-backend python infra/backup/foundation_backup.py verify \
  kya-foundation.kyabackup
```

## Exercice de restauration

La commande refuse un répertoire non vide :

```shell
uv run --package kya-platform-backend python infra/backup/foundation_backup.py restore \
  kya-foundation.kyabackup --target restore-isolated
```

Après ouverture du bundle, restaurer `neon.dump` vers une branche Neon isolée avec `pg_restore`,
importer `openfga.fga.yaml` vers un nouveau store avec `fga store import`, puis comparer les
comptages et exécuter la matrice de refus d'accès. Les métadonnées Infisical servent à vérifier la
structure et la rotation ; elles ne permettent jamais de reconstituer les valeurs secrètes.

Références officielles :

- Neon recommande un dump custom et une restauration séparée, avec URL non poolée :
  <https://neon.com/docs/import/migrate-from-neon>.
- OpenFGA fournit `store export` et `store import` :
  <https://openfga.dev/docs/modeling/store-file-format>.
- Infisical permet `viewSecretValue=false` pour une sauvegarde de métadonnées :
  <https://infisical.com/docs/api-reference/endpoints/secrets/list>.
