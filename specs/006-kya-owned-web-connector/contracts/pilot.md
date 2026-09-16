# Contrat opérationnel du pilote

## Source Data

```json
{
  "key": "kya-institutional-web",
  "name": "Site institutionnel KYA",
  "kind": "web",
  "status": "active",
  "configuration": {
    "seed_url": "https://kya-energy.com/fr",
    "allowed_hosts": ["kya-energy.com", "www.kya-energy.com"],
    "max_pages": 25,
    "max_capture_bytes": 50000000
  }
}
```

Aucun credential n'est accepté dans `configuration`. Une future source authentifiée porte
seulement une `secret_reference` Infisical opaque.

## Actif et paquet

- actif : `kya-institutional-web-capture` ;
- couche : `raw` ; classification : `public` ;
- type média : `application/vnd.kya.web-capture+json` ;
- objet : `raw/web/{asset_id}/{sha256}.json` ;
- contrat Data : JSON Schema versionné en SemVer ;
- qualité : pages présentes, réponses réussies, URL uniques, collecte complète ou avertissements.

## Déclenchement

`start_ingestion` conserve la confirmation et l'idempotence déjà imposées par le MCP. L'événement
`kya.data.run.started.v1` épingle l'unité, le pipeline, la configuration publique de la source,
l'actif et le contrat. Le worker dédié ne loue aucun autre type d'événement.
