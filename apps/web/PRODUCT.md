# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

TanStack Start, React 19 et TypeScript strict dans le monorepo KYA-Platform. Le backend métier est
FastAPI ; le navigateur n'accède directement ni à Neon, ni à OpenFGA, ni aux secrets.

## Users

- Collaborateurs KYA qui découvrent et utilisent des capacités approuvées dans leur contexte actif.
- Responsables métier qui créent, partagent, révisent et valident les méthodes de leur Direction.
- CVSI qui structure l'architecture, la plateforme, la data, la sécurité et l'industrialisation.
- Stagiaires et prestataires dont les espaces et droits sont limités dans le temps.
- Auditeurs et administrateurs qui consultent uniquement les métadonnées et preuves de leur mandat.

## Product Purpose

KYA-Platform rend le patrimoine numérique du Groupe identifiable, gouverné, partageable et
réutilisable : systèmes, applications, API, données, MCP, Skills, modèles, Design Systems et
templates. Le succès signifie qu'une personne trouve et utilise rapidement la bonne capacité sans
contourner les droits, les validations, la provenance ou l'audit.

## Positioning

La plateforme combine un catalogue gouverné, des espaces organisationnels mouvants et une même
frontière d'autorisation pour l'interface humaine et les environnements IA. Elle sépare les méthodes
encodées dans les Skills des capacités exécutables exposées par MCP.

## Operating Context

Le produit est utilisé sur les équipements courants de l'entreprise, parfois avec une bande passante
limitée. Une personne peut travailler pour plusieurs Directions, pays, équipes ou projets et doit
choisir explicitement son contexte actif. Les Directions produisent le contenu ; le CVSI fournit les
contrats, templates, contrôles et voies d'industrialisation. GitHub conserve le code, Neon les données
du Hub, Frappe/ERPNext reste un système métier référencé, OpenFGA décide les autorisations et Infisical
conserve les secrets.

## Capabilities and Constraints

- Rechercher avant affichage selon les droits, le contexte, la compatibilité et l'état.
- Publier des versions immuables après contrôles et séparation des responsabilités.
- Installer, mettre à jour et revenir en arrière depuis l'interface ou un client automatisé approuvé.
- Montrer le propriétaire, la provenance, le niveau de confiance et l'autorité de chaque élément.
- Ne jamais révéler une ressource non autorisée, une valeur secrète ou une permission implicite.
- Recalculer les droits lors de chaque changement de contexte et de chaque action sensible.
- Maintenir l'interface utilisable au clavier, sur petit écran et avec une connexion contrainte.

## Brand Commitments

Nom : KYA-Platform, pour KYA-Energy Group. Le ton est institutionnel, direct, précis et positif. La
palette de marque à préserver associe vert, orange, blanc, jaune et café. Aucun logo exploitable n'est
encore présent dans le dépôt ; l'interface ne doit pas en inventer un.

## Evidence on Hand

- Spécification fonctionnelle : `../../specs/001-platform-foundation/spec.md`.
- Modèle OpenFGA validé : `../../tests/policy/kya-platform.fga`.
- 9 scénarios et 31 décisions d'autorisation réussis.
- Contrats API, audit append-only, idempotence et modèle de références de secrets testés.
- Aucune donnée réelle d'usage, photographie, métrique de production ou témoignage n'est disponible ;
  l'interface ne doit pas en fabriquer.

## Product Principles

1. Le contexte et les droits précèdent l'affichage.
2. Une capacité doit être compréhensible avant d'être installée ou invoquée.
3. L'IA raisonne ; le logiciel exécute les opérations déterministes et auditables.
4. L'autonomie progresse avec des templates, des preuves et des validations explicites.
5. Les systèmes autoritaires restent maîtres de leurs données ; la plateforme les référence et les
   relie proprement.

## Accessibility & Inclusion

Les parcours critiques doivent fonctionner au clavier, conserver un contraste lisible, respecter la
réduction de mouvement, expliquer les états autrement que par la couleur et rester utilisables sur
des écrans et connexions modestes.
