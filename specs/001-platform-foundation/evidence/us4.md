# US4 — Systèmes et autorités de données

Date de contrôle : 2026-09-04
État : implémentation T048–T051 terminée ; enregistrement pilote factuel T052 en attente de
validation métier et de configuration.

## Garanties implémentées

- Un système possède un identifiant stable, des propriétaires métier et technique, des
  environnements, un niveau de disponibilité et des interfaces approuvées.
- Une capacité désigne son système fournisseur et son contrat ; elle ne contient pas une copie des
  données du fournisseur.
- Une autorité de données relie une catégorie, un système, un périmètre et une période semi-ouverte.
- Deux systèmes différents ne peuvent pas être autorités exclusives de la même catégorie sur le
  même périmètre et une période qui se chevauche.
- Une absence d'autorité échoue explicitement ; aucun système par défaut n'est deviné.
- La liste API des systèmes est filtrée par autorisation avant chargement. Une interface non
  approuvée n'est pas exposée.
- L'adaptateur Frappe construit des métadonnées, des contrats d'accès et des autorités ; il ne
  contient ni fiches clients, ni secret API, ni mécanisme de synchronisation caché.

Cette approche suit l'API REST officielle de Frappe : accès aux DocTypes par ressources, sélection
explicite des champs et pagination. Référence :
<https://docs.frappe.io/framework/user/en/api/rest>.

## Résultats automatisés ciblés

```text
Backend complet : 147 tests réussis — couverture 91,86 % (seuil 90 %)
Modèle d'autorité + adaptateur + API : 11 tests ciblés réussis
Interface web : 8 tests composants réussis
TypeScript : réussi
Build client et SSR : réussi
Ruff et mypy ciblés : réussis
```

Le contrôle backend remonte uniquement un avertissement de dépréciation provenant de Starlette
sur l'alias `anyio.abc.BlockingPortal`. Il ne provient pas du code KYA et ne bloque pas le jalon.

Le poste de contrôle utilise actuellement Node.js 22 alors que le projet exige Node.js 24 ou
ultérieur. Les tests, le typage et les builds réussissent néanmoins ; les environnements CI et de
déploiement doivent respecter la version déclarée par le projet.

## Contrôle visuel

L'écran « Systèmes » a été ouvert dans le navigateur local. La vue affiche distinctement :

- Frappe / ERPNext comme système métier externe ;
- les responsables métier et technique ;
- l'interface approuvée ;
- la catégorie, le périmètre, la source qui fait foi, la date et la sensibilité ;
- le principe « la plateforme conserve la règle, pas les fiches clients ».

La vue porte explicitement la mention « données de démonstration » et l'écriture non connectée est
désactivée.

## Condition de clôture T052

Les valeurs suivantes ne sont pas inventées et doivent être confirmées avant l'enregistrement réel :

1. URL de l'instance Frappe à référencer ;
2. propriétaire métier officiel du référentiel Clients ;
3. périmètre initial : Groupe entier, pays précis ou autre unité ;
4. date effective de l'autorité ;
5. DocType et champs de lecture approuvés ;
6. identité technique Frappe et référence du secret dans Infisical.

La clé ou le secret Frappe ne doit pas être communiqué tant que l'adaptateur Infisical de l'US5
n'est pas actif. Seule une référence opaque sera ensuite enregistrée.
