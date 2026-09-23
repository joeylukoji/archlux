# Comparaisons avant / après — jalon 8

Ce dossier existe parce qu'un taux ne dit pas à quoi ressemble une réparation. Les
deux chiffres du jalon 8 — **plans rendus valides** et **déplacement médian de 43 % du
côté du plan** — sont tous les deux justes et laissent croire à des choses opposées.
Ici on regarde.

> **Ce dossier a déjà servi.** C'est en regardant ces fiches qu'on a vu des pièces
> réduites à une épaisseur nulle par la correction — un plan « réparé », certifié
> valide, amputé d'une pièce. Aucune table ne le montrait : le compte de pièces restait
> juste. Le référentiel pose désormais `largeur_min = 0,50 m`, et le taux de réparation
> annoncé est passé de ~60 % à ~20 %. Voir
> [`../j8_generation.md`](../j8_generation.md), section sur le plancher de largeur.

## Comment lire une fiche

Chaque plan a deux fichiers dans le sous-dossier de son **issue** :

- `<plan>.svg` — les deux états **à la même échelle**. Une échelle par panneau
  donnerait à un plan rétréci l'air d'un plan intact ; c'est interdit par
  construction dans `export.svg.comparer`.
- `<plan>.md` — les métriques : diagnostic géométrique avant
  (`geom.diagnostic`), violations relevées par la vérification exacte
  (`certify.preuve`), puis verdict et déplacement après correction.

Conventions du tracé :

| élément | lecture |
|---|---|
| tirets rouges | le **contour visé**, tracé même si aucune pièce ne l'atteint |
| aplats semi-transparents | les pièces — un **chevauchement** se voit comme une zone plus dense |
| fond clair à l'intérieur des tirets | un **jour** : de la surface non couverte |
| un seul panneau | aucun plan n'a été produit ; redessiner l'entrée à droite se lirait « rien n'a changé » |

## Les trois issues

Huit plans par issue et par conditionnement, **échecs compris** : un dossier qui ne
montrerait que ce qui marche ne servirait à rien.

| issue | ce que ça veut dire |
|---|---|
| `réparé` | plan certifié valide — regarder le déplacement avant de conclure |
| `trame irrécupérable` | la réparation bornée ne rend pas la partition cohérente ; `deduire_trame` refuse et nomme les cellules fautives |
| `infaisable (prouvé)` | le système est **prouvé** sans solution, certificat de Farkas à l'appui — 2 à 3 contraintes en conflit sur 45 |

## Les trois jeux

HouseDiffusion lit un graphe d'accès dont dérive son `door_mask` : ni le programme ni
la topologie ne sont neutres, et mesurer sur un seul choix ne prouverait rien.

| jeu | plans | programmes | topologies |
|---|--:|---|---|
| [`etoile/`](etoile/index.md) | 320 | 8 programmes, 4 à 8 pièces | étoile — tout se rattache au séjour, le conditionnement repris tel quel de `A-AI/services/ai/app/housediff.py` |
| [`plausible/`](plausible/index.md) | 320 | les mêmes 8 | dégagement distributeur s'il existe, cuisine et salle à manger attenantes au séjour |
| [`divers/`](divers/index.md) | 100 | **25 programmes, 3 à 10 pièces** — studio, sans séjour, bureau, rangements, plusieurs bains | **les 4** : étoile, plausible, chaîne, anneau, en tourniquet |

Les 100 fiches de `divers/` y sont **toutes**, pas un échantillon : 23 réparés,
38 trames irrécupérables, 39 infaisabilités prouvées.

Les trois jeux donnent le même ordre de grandeur — 20,3 %, 17,8 %, 23,0 % — à défauts
pourtant différents : l'étoile fragmente, la chaîne fait se chevaucher. Voir
[`../j8_generation.md`](../j8_generation.md) pour les tables et le protocole.
