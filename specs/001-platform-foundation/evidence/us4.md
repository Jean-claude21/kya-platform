# US4 — Systèmes et autorités de données

Date de contrôle : 2026-09-05
État : T048–T052 terminées avec KYA Platform comme premier système factuel. Le pilote Frappe est
explicitement reporté après la fondation.

## Premier système réel

KYA Platform est retenue parce que son backend et son interface sont déjà déployés en preview et
vérifiables. L'enregistrement déclare le CVSI comme propriétaire métier, l'Équipe Informatique et
Logiciels comme responsable technique, la Business API comme interface approuvée et KYA Platform
comme autorité exclusive des métadonnées d'artefacts du Groupe à compter du 5 septembre 2026.

Cette autorité ne couvre ni les clients ni une autre donnée métier. Le test
`test_kya_platform_pilot.py` vérifie cette limite. L'écran Systèmes reprend les mêmes faits et ne
présente plus Frappe comme déjà connecté.

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
Backend complet : 210 tests réussis — couverture 90,76 % (seuil 90 %)
Pilote KYA Platform : test d'autorité ciblé réussi
Interface web : 11 tests composants réussis
Parcours Playwright : 3 tests réussis
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

La vue Systèmes affiche distinctement :

- KYA Platform comme système de gouvernance numérique actif en preview ;
- les responsables métier et technique ;
- l'interface approuvée ;
- la catégorie, le périmètre, la source qui fait foi, la date et la sensibilité ;
- la limite explicite aux données du Hub.

L'écriture non connectée reste désactivée et annoncée comme indisponible.

## Conditions du futur pilote Frappe

Les valeurs suivantes ne sont pas inventées et doivent être confirmées avant l'enregistrement réel :

1. URL de l'instance Frappe à référencer ;
2. propriétaire métier officiel du référentiel Clients ;
3. périmètre initial : Groupe entier, pays précis ou autre unité ;
4. date effective de l'autorité ;
5. DocType et champs de lecture approuvés ;
6. identité technique Frappe et référence du secret dans Infisical.

Seule une référence Infisical opaque sera enregistrée ; aucune valeur de secret ne devra entrer
dans le catalogue.
