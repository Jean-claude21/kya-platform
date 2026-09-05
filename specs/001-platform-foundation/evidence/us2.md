# Preuves US2 — Publication d'un artefact KYA

**Date d'exécution** : 2026-09-04  
**Artefact pilote** : `kya:skill:kya-business-method`  
**Version** : `0.1.0`  
**Canal** : `pilot`

## Chaîne démontrée

1. La Direction pilote possède la méthode et soumet une version candidate.
2. Le contenu est figé sur le commit source
   `ddbb9c688e83d5d1016c691a6673a00b7f8ab5ae`.
3. Le réviseur contrôle le format, la provenance et l'absence de secret.
4. Une personne distincte approuve la publication.
5. Le service de release publie exactement le contenu approuvé dans
   `catalog/releases/kya-business-method/0.1.0/`.

Personas d'exécution : Diana soumet, Chloé révise, Alice approuve et l'identité technique
`cvsi-release-service` publie. Ces noms constituent une matrice de test, pas l'affirmation d'une
décision humaine réelle.

## Preuves

- Contrat manifeste : valide.
- Validateur de Skill : réussi.
- Séparation auteur/réviseur/approbateur/exécuteur : quatre identités distinctes.
- Empreinte du fichier source Git :
  `094762a78dd0a27b71a86ba791941c210256b705ef426504251c41cb7060bb74`.
- Le test de contrat relit le fichier depuis l'objet Git et recalcule SHA-256 ; toute substitution
  du contenu ou du commit fait échouer le contrôle.
- Le workflow applicatif produit ses événements via l'outbox dans la même transaction que chaque
  changement d'état.

## Limite volontaire

Cette première publication prouve le chemin local et Git du canal pilote. Elle ne constitue ni une
mise à disposition Groupe ni une installation sur un poste utilisateur ; ces preuves appartiennent
à US3 après mise en place de la découverte, de l'installation et du rollback.
