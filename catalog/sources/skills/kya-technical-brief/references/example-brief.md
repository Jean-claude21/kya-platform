# Exemple - Choix du moteur de file d'attente

**Contexte** - Le service de generation de rapports sature aux heures de pointe. Les traitements sont aujourd'hui synchrones.

**Probleme** - Absorber les pics de charge sans degrader le temps de reponse de l'API.

**Options**

| Option | Benefice | Cout | Risque |
|---|---|---|---|
| File Redis | Simple, deja deploye | Faible | Perte de messages si Redis tombe |
| RabbitMQ | Garanties de livraison | Moyen | Nouvelle brique a exploiter |
| Table de jobs en base | Aucune dependance nouvelle | Faible | Contention sur la base |

**Decision** - File Redis avec persistance activee : cout d'adoption le plus bas pour le volume actuel.

**Prochaines etapes**

1. Activer la persistance Redis - responsable technique - S+1
2. Migrer la generation de rapports en asynchrone - equipe backend - S+3
3. Mettre en place une alerte sur la profondeur de file - responsable technique - S+3

_Exemple illustratif : les elements ci-dessus ne refletent aucune decision reelle._
