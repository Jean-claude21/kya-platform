# Benchmark de déploiement — Dokploy et Coolify

## Protocole commun

Le même protocole doit être exécuté sur les deux fournisseurs, avec le même commit validé :

1. épingler le SHA Git exact ;
2. appliquer les migrations Neon avant la bascule ;
3. déployer les images Web et Backend issues des Dockerfiles du monorepo ;
4. attendre l'état sain du fournisseur ;
5. vérifier `/api/v1/health/ready` et la page Web par HTTP ;
6. mesurer le délai de mise en service et exécuter un rollback vers le dernier SHA sain ;
7. confirmer qu'aucune valeur secrète n'apparaît dans les journaux et artefacts.

## Résultat Coolify Cloud — 5 septembre 2026

- Branche : `dev`.
- Commit validé et déployé : `54aaa3163cb238d64958d4460818a9a10bff8b5b`.
- Backend : déploiement terminé, état `running:healthy`, disponibilité HTTP 200.
- Web : déploiement terminé, état `running:healthy`, disponibilité HTTP 200.
- Migration : révision Neon `20260904_0003`, puis exécution pré-déploiement idempotente réussie.
- Déterminisme : l'adaptateur épingle désormais `DeploymentRequest.commit_sha` avant le lancement.
- Incident d'amorçage corrigé : périmètre preview des variables, apostrophes importées et paramètres
  Neon incompatibles avec `asyncpg`.

## Résultat Dokploy

Non exécuté : aucune instance, URL d'API, identité machine ou application Dokploy n'est encore
configurée. Cette absence ne permet ni une mesure équivalente ni une décision factuelle.

## Décision provisoire

Coolify est le fournisseur de test opérationnel. Dokploy demeure une cible supportée par contrat,
mais aucune préférence définitive ne sera déclarée avant l'exécution du même protocole sur une
instance Dokploy. Le critère de choix portera sur la fiabilité, le temps de promotion, le rollback,
la sécurité des secrets, l'observabilité et le coût d'exploitation.
