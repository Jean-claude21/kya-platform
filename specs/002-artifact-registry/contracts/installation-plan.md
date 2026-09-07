# Contrat — plan d'installation gouverné

## Frontière de confiance

`request_install` n'installe rien. Après contrôle OAuth et OpenFGA, le Registry charge une release
publiée depuis Neon, vérifie son digest et sa signature Ed25519, puis contrôle la compatibilité du
profil et de la version du client. Il retourne un plan immuable. Le client reste seul responsable de
l'affichage de la cible, du consentement et des écritures locales.

## Entrée minimale

- `release_id`, `target`, `profile`, `scope`, `client_version` ;
- clé d'idempotence forte ;
- confirmation explicite structurée.

Profils : `codex`, `claude-code`, `portable-zip`. Portées : `personal`, `project`.

## Sortie

Le plan contient l'identité de la release, son digest, le locator adressé, la contrainte de
compatibilité, la destination symbolique et exactement sept actions typées :

1. télécharger le paquet dans une zone temporaire ;
2. vérifier la signature de release ;
3. vérifier le digest du contenu ;
4. vérifier la compatibilité du client ;
5. préparer les fichiers sans activation ;
6. activer atomiquement dans la destination consentie ;
7. écrire un reçu local pour audit et rollback.

Le plan ne contient aucune commande shell, aucune valeur de secret et aucun chemin absolu imposé
par le serveur. À release, cible, profil, portée et version client identiques, son UUID est stable.

## Destinations symboliques

| Profil | Personnel | Projet |
|---|---|---|
| Codex | `${CODEX_PERSONAL_SKILLS_DIR}/{slug}` | `.agents/skills/{slug}` |
| Claude Code | `~/.claude/skills/{slug}` | `.claude/skills/{slug}` |
| Zip portable | `${USER_SELECTED_DIRECTORY}/{slug}-{version}.zip` | identique |

Codex et Claude Code n'acceptent ici que les artefacts `skill`. Les autres types passent par le zip
portable jusqu'à l'existence d'un installateur spécifique, testé et gouverné.
