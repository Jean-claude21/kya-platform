# Plan — Veilles gouvernées KYA Intelligence

## Architecture

```text
Sources planifiées -> snapshots -> contenu gouverné
                                      |
API / MCP -> IntelligenceService -> recherche bornée -> signaux citables Neon
                                      |
                               audit + outbox
                                      |
                     Claude / ChatGPT analyse et programme
```

Le domaine `intelligence` reste un module du monolithe. Il référence les fragments de contenu du
domaine Data sans les recopier comme nouvelle vérité. Le premier incrément fournit domaine, service,
stockage PostgreSQL, Business API, outils MCP et tests. Un worker événementiel pourra ensuite
évaluer automatiquement les veilles à la fin d'une ingestion sans changer les contrats publics.

## Contrôle constitutionnel

- Spec Kit et traçabilité : conforme.
- Neon reste autoritaire pour l'état propre au Hub : conforme.
- Autorisation contextualisée par unité et refus par défaut : conforme.
- IA pour le raisonnement, logiciel déterministe pour la détection : conforme.
- Preuves citables, audit, idempotence et réversibilité : conforme.

## Retour arrière

Désactiver routes et outils MCP, puis arrêter toute consommation événementielle. Les tables
additives peuvent rester en lecture pour audit ; aucun contenu source n'est modifié.
