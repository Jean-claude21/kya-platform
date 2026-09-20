# Plan d'implémentation

1. Étendre le manifeste universel sans rupture de compatibilité.
2. Exposer un registre d'applications permission-first.
3. Étendre le SDK existant et publier une nouvelle version immuable.
4. Relier le shell KYA-Platform au registre réel.
5. Réutiliser KYA Data Foundation pour les schémas versionnés et la rétention ; ajouter les modèles
   d'enregistrements avec KYA Forms, lorsque le premier cas métier fixe les invariants nécessaires.
6. Standardiser l'enveloppe d'événement et la signature des webhooks.
7. Renforcer les templates, CI/CD, Infisical, santé et supervision.
8. Valider le tout avec la première version de KYA Forms.

Le moteur de formulaires, le moteur de workflow et le constructeur de dashboards restent des
produits séparés. Ils consomment ce socle au lieu d'être absorbés dans KYA-Platform.
