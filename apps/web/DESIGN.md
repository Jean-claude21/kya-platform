---
name: KYA Platform
description: Un tableau de conduite énergétique sobre pour parcourir, comprendre et gouverner les capacités numériques.
colors:
  forest-deep: '#073b25'
  forest-structural: '#145a32'
  forest-signal: '#1f8a4c'
  forest-wash: '#e6f3e9'
  action-orange: '#d85f00'
  decision-orange: '#a84300'
  orange-wash: '#fff0e2'
  warning-amber: '#9a6500'
  amber-wash: '#fff4c5'
  restricted-coffee: '#6b4b3e'
  control-ink: '#17211b'
  muted-ink: '#5b665f'
  circuit-line: '#dfe5de'
  warm-ground: '#f7f4ed'
  control-surface: '#ffffff'
typography:
  display:
    fontFamily: 'Aptos, Segoe UI Variable, Segoe UI, sans-serif'
    fontSize: 'clamp(24px, 2vw, 32px)'
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: '-0.025em'
  headline:
    fontFamily: 'Aptos, Segoe UI Variable, Segoe UI, sans-serif'
    fontSize: '20px'
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: '-0.025em'
  title:
    fontFamily: 'Aptos, Segoe UI Variable, Segoe UI, sans-serif'
    fontSize: '15px'
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: 'Aptos, Segoe UI Variable, Segoe UI, sans-serif'
    fontSize: '14px'
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: 'Aptos, Segoe UI Variable, Segoe UI, sans-serif'
    fontSize: '12px'
    fontWeight: 680
    lineHeight: 1.3
rounded:
  sm: '8px'
  node: '10px'
  md: '12px'
spacing:
  xs: '4px'
  sm: '8px'
  md: '12px'
  lg: '16px'
  xl: '20px'
  2xl: '24px'
  3xl: '32px'
  4xl: '44px'
components:
  button-primary:
    backgroundColor: '{colors.forest-structural}'
    textColor: '{colors.control-surface}'
    typography: '{typography.body}'
    rounded: '{rounded.sm}'
    padding: '0 16px'
    height: '40px'
  button-primary-hover:
    backgroundColor: '{colors.forest-deep}'
    textColor: '{colors.control-surface}'
  button-decision:
    backgroundColor: '{colors.decision-orange}'
    textColor: '{colors.control-surface}'
    typography: '{typography.label}'
    rounded: '{rounded.sm}'
    padding: '0 12px'
    height: '36px'
  icon-button:
    backgroundColor: 'transparent'
    textColor: '{colors.control-ink}'
    rounded: '{rounded.sm}'
    height: '40px'
    width: '40px'
  search-field:
    backgroundColor: '{colors.control-surface}'
    textColor: '{colors.control-ink}'
    typography: '{typography.body}'
    rounded: '{rounded.sm}'
    padding: '0 12px'
    height: '42px'
  status-label:
    backgroundColor: 'transparent'
    textColor: '{colors.muted-ink}'
    typography: '{typography.label}'
  panel:
    backgroundColor: '{colors.control-surface}'
    textColor: '{colors.control-ink}'
    rounded: '{rounded.md}'
    padding: '20px'
  capability-node:
    backgroundColor: '{colors.control-surface}'
    textColor: '{colors.forest-deep}'
    typography: '{typography.label}'
    rounded: '{rounded.node}'
    padding: '12px'
    height: '92px'
---

# Design System: KYA Platform

## Overview

**Creative North Star: "Le tableau de conduite énergétique"**

KYA Platform se présente comme une salle de conduite claire : un fond chaud et calme accueille des surfaces blanches, tandis que le vert structure la lecture et que l’orange signale les décisions. Les relations entre capacités forment un circuit lisible plutôt qu’un décor ; l’interface rend la provenance, l’état et l’autorité visibles avant l’action.

Le système est institutionnel, direct et dense sans être encombré. Il privilégie les lignes fines, les libellés précis, les états explicites et les gestes prévisibles. Il refuse les tableaux de bord SaaS composés de tuiles sans relations, les animations gratuites et tout logo ou police prétendument officiel sans actif fourni.

**Key Characteristics:**

- Fond ivoire chaud, surfaces blanches et séparateurs gris-vert.
- Vert profond pour la structure et la confiance ; orange sombre pour les décisions.
- Réseau de dépendances comme motif fonctionnel et signature visuelle.
- Densité opérationnelle, hiérarchie compacte et vocabulaire d’état toujours textuel.
- Comportements sobres, clavier en premier et réduction de mouvement respectée.

## Colors

La palette associe des verts forestiers institutionnels à un fond papier chaud ; l’orange, le jaune et le café restent des signaux rares et sémantiques.

### Primary

- **Vert forêt profond** (`forest-deep`): ancre les titres, les notifications fortes et les surfaces de confirmation.
- **Vert structurel** (`forest-structural`): porte les actions principales, icônes de couche, comptes et navigation active.
- **Vert signal** (`forest-signal`): indique la santé, le focus et les relations positives.
- **Voile végétal** (`forest-wash`): soutient les survols, résumés et regroupements sans ajouter d’ombre.

### Secondary

- **Orange d’action** (`action-orange`): point lumineux des états qui réclament de l’attention.
- **Orange de décision** (`decision-orange`): accent plus sombre réservé aux compteurs, sélections et décisions gouvernées.
- **Voile orange** (`orange-wash`): fond léger disponible pour les messages d’attention.

### Tertiary

- **Ambre d’alerte** (`warning-amber`): avertissement non bloquant, toujours accompagné d’un libellé.
- **Voile ambré** (`amber-wash`): fond d’avertissement doux.
- **Café restreint** (`restricted-coffee`): accès limité, dépendance restreinte et icône de protection.

### Neutral

- **Encre de conduite** (`control-ink`): texte principal et information à forte priorité.
- **Encre secondaire** (`muted-ink`): descriptions, métadonnées et libellés de soutien.
- **Ligne de circuit** (`circuit-line`): bordures, séparateurs et structure de tableau.
- **Sol chaud** (`warm-ground`): toile générale de l’application.
- **Surface de contrôle** (`control-surface`): panneaux, champs et cartes interactives.

### Named Rules

**The Signal, Not Decoration Rule.** Le vert construit le parcours ; l’orange, l’ambre et le café n’apparaissent que pour exprimer une décision, un avertissement ou une restriction.

**The Text Completes Color Rule.** Aucun état, droit ou avertissement ne repose sur la couleur seule : point, libellé et contexte voyagent ensemble.

## Typography

**Display Font:** Aptos (avec Segoe UI Variable, Segoe UI et sans-serif en repli)
**Body Font:** Aptos (avec Segoe UI Variable, Segoe UI et sans-serif en repli)

**Character:** Une sans-serif système nette et familière donne à l’interface une voix institutionnelle sans coût réseau. Les contrastes viennent de la taille, du poids et de l’espacement, pas d’une police décorative non disponible.

### Hierarchy

- **Display** (700, `display`, 1.2): titre principal de la surface, compact et légèrement resserré.
- **Headline** (700, `headline`, 1.25): titres de panneaux et de sections.
- **Title** (700, `title`, 1.35): intitulés de décisions et contenus prioritaires de carte.
- **Body** (400, `body`, 1.5): explications et textes courants, avec une mesure maximale observée de 70 caractères.
- **Label** (680, `label`, 1.3): statuts, métadonnées et repères denses ; les en-têtes de tableau utilisent les capitales avec un léger espacement.

### Named Rules

**The System Voice Rule.** Aptos et ses replis système restent la seule pile tant qu’aucune police institutionnelle officielle n’est fournie.

**The Compact Hierarchy Rule.** Les écrans d’opération utilisent peu de niveaux, nettement différenciés ; les libellés compacts ne deviennent jamais le corps de lecture.

## Layout

Le shell associe une barre supérieure collante de 68 px, une navigation horizontale de 50 px et un contenu centré limité à 1680 px. Au-dessus de 1100 px, la zone principale réserve 320 px à la file de décisions et laisse le réseau occuper l’espace restant ; en dessous, les panneaux s’empilent. Les espacements usuels suivent la progression documentée de 4 à 32 px, avec 44 px réservé aussi aux grandes marges et cibles tactiles.

Le réseau garde six colonnes et autorise le défilement horizontal sur grand écran étroit. À 720 px et moins, il devient un rail de couches de 78 vw avec accrochage horizontal ; la topologie SVG s’efface au profit d’un parcours séquentiel explicite. Les contrôles de navigation de couche mesurent au moins 44 × 44 px. Les tableaux conservent leur structure et défilent horizontalement plutôt que de compresser les données.

**The Context Before Content Rule.** Le contexte organisationnel reste visible dans le shell, y compris lorsqu’il passe sur une deuxième ligne sous 1100 px.

**The 44-Pixel Mobile Rule.** Tout contrôle de parcours de couche sur petit écran offre une cible de 44 × 44 px, même si son glyphe est plus petit.

## Elevation & Depth

Le système est plat par défaut : panneaux et tables sont séparés par la teinte, une bordure de 1 px et l’espacement. L’ombre est une réponse fonctionnelle, réservée aux nœuds survolés, au nœud sélectionné et au toast flottant ; elle ne transforme pas chaque contenant en carte surélevée.

### Shadow Vocabulary

- **Nœud au repos** (`node-rest`): ombre très légère qui distingue un élément cliquable du réseau.
- **Relief interactif** (`raised`): profondeur verte diffuse lors du survol d’un nœud.
- **Décision sélectionnée** (`selected`): halo orange discret qui relie l’élévation à l’état choisi.
- **Notification flottante** (`toast`): ombre plus ample pour détacher un message temporaire du shell.
- **Focus accessible** (`focus`): anneau vert de 3 px sur boutons, champs et liens au clavier.

### Named Rules

**The Flat Until Active Rule.** Une surface reste bordée et plate au repos ; l’élévation signale une interaction, une sélection ou une notification.

## Shapes

Les panneaux utilisent des coins doucement arrondis (`md`), les contrôles et résumés un rayon plus serré (`sm`), et les nœuds un intermédiaire (`node`). Les badges d’état et compteurs emploient des points ou cercles pleins ; les lignes de relation restent fines, courbes et non décoratives. Les bordures sont généralement de 1 px, pleines pour la structure et en tirets uniquement pour une restriction ou un emplacement vide.

**The Soft Instrument Rule.** Les coins sont accueillants mais compacts : pas de capsules généralisées ni de rayons exagérés sur les grands panneaux.

## Components

Les composants ressemblent à des instruments fiables : compacts, explicites et calmes au repos, avec des états nettement visibles.

### Buttons

- **Shape:** rectangle doucement arrondi (`sm`), hauteur principale de 40 px et espacement horizontal de 16 px.
- **Primary:** vert structurel sur surface blanche, poids 700 ; le survol passe au vert forêt profond.
- **Decision:** orange de décision, format compact de 36 px ; il est réservé aux actions de gouvernance réellement disponibles.
- **Hover / Focus:** changement tonal immédiat et anneau de focus vert ; les contrôles désactivés gardent leur libellé, un curseur non autorisé et une opacité réduite.
- **Icon:** carré de 40 px sur ordinateur ; sur mobile, les contrôles de parcours critiques passent à 44 px.

### Chips

- **Style:** libellé compact avec point de 8 px ; texte et point partagent le même sens sémantique.
- **State:** sain en vert, attention en orange, avertissement en ambre, restriction en café et neutre en gris.

### Cards / Containers

- **Corner Style:** panneaux en `md`, nœuds en `node`.
- **Background:** surface de contrôle sur sol chaud.
- **Shadow Strategy:** aucune ombre sur les panneaux ; élévation uniquement pour les nœuds interactifs et les notifications.
- **Border:** ligne de circuit de 1 px ; bordure verte pour une relation, orange pour une sélection.
- **Internal Padding:** 20 px sur ordinateur, 16 px sur mobile ; 12 px dans un nœud.

### Inputs / Fields

- **Style:** surface blanche, bordure de circuit, rayon `sm`, hauteur minimale de 42 px et icône de recherche adjacente.
- **Focus:** bordure vert signal et anneau de focus visible.
- **Disabled:** aucune ambiguïté entre saisie indisponible et simple texte ; conserver un état natif explicite.

### Navigation

La navigation principale est un rail horizontal blanc. Les entrées ont un poids de 650, un survol sur voile végétal et un état actif en vert souligné par un trait de 3 px. Sur mobile, le rail défile horizontalement ; les destinations non câblées sont désactivées et annoncées comme « bientôt » dans leur aide.

### Capability Network

Le réseau est la signature du système. Chaque couche associe un pictogramme vert, un titre et un compteur ; chaque nœud combine nom, type, détail et état. Les relations normales sont vert clair, les restrictions café en tirets et la relation active orange sombre. Sur mobile, la séquence de couches remplace la topologie pour préserver la compréhension et le toucher.

### Decision Queue

La file place le nombre de décisions dans un cercle orange sombre, puis sépare chaque décision par une ligne. Une action future n’imite jamais une action disponible : elle reste désactivée et porte le suffixe « bientôt » ou une aide équivalente.

## Do's and Don'ts

### Do:

- **Do** utiliser le vert pour la structure, la santé et le focus, puis réserver l’orange sombre aux décisions et sélections.
- **Do** accompagner chaque couleur d’état d’un point, d’un libellé et du contexte nécessaire.
- **Do** conserver le réseau comme explication navigable des dépendances et des droits.
- **Do** maintenir les cibles critiques de navigation mobile à 44 × 44 px minimum.
- **Do** désactiver et marquer « bientôt » toute action visible qui n’est pas encore reliée au produit.
- **Do** respecter `prefers-reduced-motion` et garder les transitions brèves et fonctionnelles.

### Don't:

- **Don't** inventer un logo, une typographie officielle, une métrique d’usage ou une preuve absente du produit.
- **Don't** remplacer les relations par une grille de cartes indépendantes ou une animation décorative.
- **Don't** utiliser l’orange clair pour un compteur de décision lorsque l’orange sombre assure le contraste requis.
- **Don't** ajouter des ombres à chaque panneau : la bordure et la hiérarchie tonale suffisent au repos.
- **Don't** présenter une action future comme cliquable ou compter uniquement sur une infobulle pour expliquer son indisponibilité.
