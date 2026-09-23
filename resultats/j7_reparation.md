# Jalon 7 — reparation de plans MSD corrompus

Corpus MSD, 300 appartements reels, 4796 corruptions,
graine racine 17. Chaque plan corrompu est soumis aux **deux** modes ; *repli* est
la strategie applicable : tenter `pavage=True`, retomber sur `legalize` seul si la
trame n'est pas recuperable. **0,0 %** des plans corrompus sont valides avant
correction.


| Faute | n | `legalize` | `pavage=True` | repli | IC 95 % | t median |
|---|--:|--:|--:|--:|:--:|--:|
| jour (`retrecir`) | 1196 | 10.0 % | 97.6 % | **98.0 %** | [97.0, 98.6] | 6.5 ms |
| sous-dimension (`aplatir`) | 1200 | 4.8 % | 96.0 % | **96.3 %** | [95.1, 97.3] | 6.5 ms |
| chevauchement (`elargir`) | 1200 | 68.2 % | 90.3 % | **91.2 %** | [89.5, 92.7] | 6.5 ms |
| decalage (`deplacer`) | 1200 | 60.8 % | 88.1 % | **90.0 %** | [88.2, 91.6] | 6.6 ms |
| **toutes fautes** | 4796 | 35.9 % | 93.0 % | **93.9 %** | [93.2, 94.5] | 6.5 ms |

| amplitude 0.1 m | 1199 | 37.3 % | 96.3 % | **96.8 %** | [95.7, 97.7] | 6.4 ms |
| amplitude 0.25 m | 1200 | 37.8 % | 96.3 % | **96.9 %** | [95.8, 97.8] | 6.5 ms |
| amplitude 0.5 m | 1199 | 35.0 % | 92.0 % | **93.2 %** | [91.7, 94.5] | 6.5 ms |
| amplitude 1.0 m | 1198 | 33.6 % | 87.3 % | **88.6 %** | [86.6, 90.2] | 6.7 ms |

## Lecture

Sans contrainte de pavage, les separations du polytope sont des **inegalites** : un
plan troue est deja le point le plus proche de lui-meme, l'optimum L1 le laisse tel
quel, et la verification exacte le rejette. D'ou moins de 10 % sur les jours contre
68 % sur les chevauchements.

`pavage=True` impose les incidences bord/ligne de la trame recuperee. La condition de
pavage etant **combinatoire** — elle ne porte que sur les indices, jamais sur les
coordonnees — tout point admissible devient un pavage exact : un jour cesse d'etre
representable. Le systeme reste faisable par construction ; aucun LP infaisable
n'a ete observe.

La recuperation de la trame combine deux mecanismes sans aucun seuil en metres : la
resorption des lignes **orphelines** (support < 2), puis une **reparation bornee**
de la partition, qui agrandit ou retrecit une piece d'un cran tant que les cellules
concernees sont toutes manquantes, ou toutes en exces. Budget 4 : au-dela, la faute
n'est plus une cote fausse mais une incoherence d'ordre, et `deduire_trame` refuse.

## Limites

Ces perturbations ne sont **pas** un modele des erreurs d'un generateur particulier :
elles reproduisent les familles de fautes rapportees par la litterature, sans en
calibrer les frequences. La table doit etre completee par au moins un generateur
public avant publication.

La reparation peut **absorber une piece manquante dans sa voisine** : fermer un jour,
c'est agrandir quelqu'un. Le plan sort alors avec une piece de moins que prevu. Un
appelant qui doit preserver le programme piece par piece passe `budget_reparation=0`.
