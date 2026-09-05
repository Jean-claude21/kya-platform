# Preuve T071 — Accessibilité et faible bande passante

Date : 2026-09-05

Le parcours Playwright couvre trois risques de la fondation :

- navigation principale identifiable, focus clavier visible et activation au clavier ;
- titres, tableau d'autorité et système pilote exposés avec des rôles accessibles ;
- viewport 360 × 800 sans débordement horizontal de page ;
- contenu principal rendu lorsque chaque ressource non-document est retardée de 200 ms ;
- préférence de réduction de mouvement activée pendant les contrôles.

Le test ne prétend pas remplacer un audit WCAG complet avec technologies d'assistance. Il constitue
une barrière de régression automatisée sur le parcours critique de la fondation.
