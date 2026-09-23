# Jalon 8 — synthèse : légaliser des plans **réellement générés**

Synthèse des trois exécutions de `experiences/j8_generation.py`. Les tables détaillées
sont dans `j8_etoile.md`, `j8_plausible.md` et `j8_divers.md`, les mesures individuelles
dans les CSV de même préfixe. Les comparaisons **avant / après**, plan par plan, sont
dans [`visuels/`](visuels/index.md).

## Protocole

**Générateur.** HouseDiffusion (Shabani, Hosseini, Furukawa, *CVPR 2023*), poids
officiels `model250000.pt`, entraîné sur RPLAN. Sortie **vectorielle** : aucune
vectorisation d'image ne s'interpose entre le modèle et la mesure.

**Échantillonnage à 1000 pas, sans rééchantillonnage.** `gaussian_diffusion.py:270`
n'active la branche de débruitage **discret** — celle qui aligne les coins sur la
grille, et la contribution centrale du papier — que pour `t < 32`. Sous-échantillonner
la trajectoire la court-circuite et fabrique un désalignement qui n'appartient pas au
modèle :

| pas | écart médian d'un coin à son rectangle axé |
|--:|--:|
| 20 | 0,750 m |
| 80 | 0,188 m |
| 200 | **0,000 m** |
| 1000 | **0,000 m** |

À 1000 pas les pièces générées sont **exactement** axées : aucune approximation par
boîte englobante n'entre dans ce qui suit.

**Trois jeux, deux axes de diversité.** HouseDiffusion lit un graphe d'accès, dont
dérive le `door_mask` : deux pièces non reliées ne s'attirent aucune attention. Ni le
programme ni la topologie ne sont donc neutres, et un seul choix ne prouverait rien.

| jeu | plans | programmes | topologies |
|---|--:|---|---|
| *étoile* | 320 | 8, de 4 à 8 pièces | étoile : tout se rattache au séjour |
| *plausible* | 320 | les mêmes 8 | dégagement distributeur s'il existe, séjour sinon |
| *divers* | 100 | **25, de 3 à 10 pièces** | **les 4**, en tourniquet |

Le catalogue *divers* couvre ce que les deux premiers n'atteignent pas : le studio à
trois pièces, les programmes sans séjour ou sans cuisine, le bureau, les rangements,
les doubles salles de bains, et jusqu'à dix pièces. Ses quatre topologies sont
l'étoile, le graphe plausible, la **chaîne** (enfilade, le moins d'arêtes possible) et
l'**anneau** (la chaîne refermée, seule à porter un cycle). La topologie tourne en
tourniquet sur les programmes triés par taille, si bien qu'elle ne colle à aucune
taille : 5,50 à 6,17 pièces en moyenne selon la topologie.

Aucune n'est un graphe du jeu de test RPLAN, qui n'est pas librement
accessible. Ces chiffres décrivent donc le modèle **sous conditionnement synthétique**
— c'est-à-dire le régime de déploiement réel, celui où un utilisateur demande « deux
chambres, cuisine ouverte », et non le régime du benchmark.

**Échelle.** Les coordonnées RPLAN sont sans unité. Le facteur est calé pour que l'aire
médiane générée vaille celle d'un appartement MSD (79,0 m², mesurée sur 1 200
appartements), afin que les déplacements des jalons 7 et 8 soient comparables. Aucun
taux de validité n'en dépend : chevauchement et jour sont invariants d'échelle.

740 plans en tout, graine racine 17.

## Ce que le générateur produit

| | étoile | plausible | divers |
|---|--:|--:|--:|
| plans valides avant correction | **0 / 320** | **0 / 320** | **0 / 100** |
| pièces recouvertes par pièce | 0,80 | 1,60 | 1,00 |
| part de jour dans l'enveloppe | 28,6 % | 24,7 % | 28,7 % |
| dont trous **intérieurs** | 0,0 % | 0,0 % | 0,0 % |
| morceaux disjoints de l'union | **4** | **2** | **3** |
| cellules de la trame implicite | **80** | 64 | 64 |

Le graphe d'accès échange des jours contre des chevauchements — il recolle une partie
de l'archipel au prix de recouvrements deux fois plus nombreux — mais **aucun des
740 plans générés n'est valide**, sous aucun des trois conditionnements.

Les trous strictement intérieurs sont nuls : le « jour » n'est pas un percement, c'est
de l'espace **entre** des îlots de pièces. C'est ce que confirme le nombre de morceaux.

Le chiffre décisif est celui des cellules : 64 à 80 cellules de trame pour 6 pièces.
Dans un plan réel les pièces partagent leurs murs et ce nombre reste petit. Ici presque
aucune coordonnée ne coïncide — la structure combinatoire dont dépend `geom.pavage`
n'est pas seulement violée, elle est **absente**.

Pour situer : les auteurs de MSD rapportent que leur propre baseline produit des pièces
qui en recouvrent **4,11 ± 2,25** autres, et que « overall, the floor plans often look
infeasible ». Le mode de défaillance mesuré ici n'est donc pas un accident de ce
modèle-là.

## Réparation

Taux de plans **certifiés valides** après correction, intervalles de Wilson à 95 %.

Référentiel `largeur_min = 0,50 m` — voir la section suivante, ce choix est décisif.

| mode | budget | étoile (n=320) | plausible (n=320) | divers (n=100) |
|---|--:|--:|--:|--:|
| `legalize` seul | — | **0,0 %** [0,0–1,2] | **0,0 %** [0,0–1,2] | **0,0 %** [0,0–3,7] |
| `pavage=True` | 0 | 0,6 % [0,2–2,2] | 0,6 % [0,2–2,2] | 3,0 % [1,0–8,5] |
| `pavage=True` | 4 | 10,9 % [8,0–14,8] | 10,6 % [7,7–14,5] | 17,0 % [10,9–25,5] |
| `pavage=True` | 8 | 18,4 % [14,6–23,1] | 16,6 % [12,9–21,0] | 23,0 % [15,8–32,2] |
| `pavage=True` | 16 | **20,3 %** [16,3–25,1] | **17,8 %** [14,0–22,4] | **23,0 %** [15,8–32,2] |

Déplacement médian à budget 16 : 43 %, 38 % et 43 % du côté du plan. Médiane de 0,8 à
3,6 ms par correction dans tous les cas.

**Les trois jeux donnent le même ordre de grandeur** — 20,3 %, 17,8 %, 23,0 % — alors
qu'ils ne produisent pas les mêmes défauts et que le troisième couvre trois fois plus
de programmes et quatre topologies. C'est ce qui autorise à lire ces taux comme une
propriété du couple générateur / légaliseur, et non du conditionnement qu'on lui a
donné.

## Le plancher sur la largeur n'est pas un détail de conformité

Sans plancher strictement positif, **le moyen le moins coûteux de fermer un jour est de
réduire une pièce à zéro**. Le plan sort alors « valide » et certifié — il pave
exactement son contour — amputé d'une pièce que le tracé ne montre même plus. Compter
les pièces ne le détecte pas : une pièce écrasée à 0 m reste dans le compte.

À budget 16, selon le seuil :

| `largeur_min` | étoile : valides / **intacts** | plausible | divers | plus petit côté (étoile) |
|--:|--:|--:|--:|--:|
| **0,00 m** | 60,9 % / **19,1 %** | 59,7 % / **13,8 %** | 59,0 % / **20,0 %** | **0,000 m** |
| 0,25 m | 20,3 % / 19,1 % | 17,8 % / 13,8 % | 23,0 % / 20,0 % | 1,360 m |
| **0,50 m** *(nominal)* | 20,3 % / **20,3 %** | 17,8 % / **17,8 %** | 23,0 % / **23,0 %** | 1,360 m |
| 1,00 m | 20,3 % / 20,3 % | 17,8 % / 17,8 % | 23,0 % / 23,0 % | 1,360 m |
| 1,80 m *(réglementaire)* | 20,3 % / 20,3 % | 17,8 % / 17,8 % | 22,0 % / 22,0 % | 1,800 m |

« Intact » = certifié valide **et** aucune pièce sous 50 cm.

Deux lectures s'imposent.

**Le taux est plat de 0,25 m à 1,80 m.** Ce n'est donc pas une affaire de calibrage de
seuil : c'est binaire. Soit on autorise l'annihilation et on obtient ~60 % de plans dont
les deux tiers sont mutilés, soit on l'interdit et on obtient ~20 % de plans entiers.
Exiger la largeur réglementaire de 1,80 m ne coûte rien de plus que d'exiger 25 cm.

**Le jalon 7 avait raison de poser `largeur_min = 0`, le jalon 8 avait tort de le
recopier.** Sur MSD, un seuil à 1,80 m cassait 52 plans **déjà valides** sur 60 : la
prudence était fondée. Ici, 0 / 740 plans générés sont valides au départ — le seuil ne
peut donc rien casser, et son absence ne fait qu'ouvrir une porte de sortie dégénérée
au solveur.

### `legalize` seul répare exactement zéro plan

Ce n'est pas une contre-performance, c'est la prédiction de `geom.pavage` vérifiée sur
données réelles. Les séparations du polytope sont des **inégalités** : un plan troué est
déjà le point le plus proche de lui-même, l'optimum L1 le laisse tel quel, et la
vérification exacte le rejette. Là où le jalon 7 laissait 35,9 % de réussite au mode de
base — parce qu'un plan corrompu couvre encore son contour — une sortie de générateur
n'en laisse aucune.

### Le budget par défaut est calé sur le mauvais régime

`legalize` figeait `budget_reparation` à 4, valeur ajustée sur des plans corrompus où la
faute est une cote fausse et se résorbe en un cran. Ici le taux triple entre 4 et 16,
puis sature. Le paramètre est désormais exposé.

### Ce qui gouverne le taux : la taille de la trame

Ce n'est **pas** la connexité — les plans d'un seul tenant ne se réparent pas mieux
(16,7 % à 1 morceau contre 70,7 % à 4, sur des effectifs déséquilibrés). C'est le nombre
de pièces, via la taille de la trame :

| pièces | étoile | plausible | divers | cellules médianes |
|--:|--:|--:|--:|--:|
| 3 | — | — | 66,7 % | 16 |
| 4 | 75,0 % | 75,0 % | 68,8 % | 30 |
| 5 | 77,5 % | 80,0 % | 65,0 % | 48 |
| 6 | 65,0 % | 60,0 % | 81,2 % | 72 |
| 7 | 48,3 % | 49,2 % | 50,0 % | 84 |
| 8 | 47,5 % | 35,0 % | 33,3 % | 118 |
| 9 | — | — | 25,0 % | 131 |
| 10 | — | — | *50,0 %* (n=4) | 181 |

La relation est monotone et s'explique : quand aucun bord ne coïncide, la trame enfle en
\\((2n-1)^2\\), alors que la réparation bornée ne corrige qu'un nombre borné de cellules.

Le catalogue *divers* étend la courbe aux deux bouts — le studio à trois pièces monte à
66,7 %, le neuf-pièces tombe à 25 %. La case à dix pièces ne compte que quatre plans :
elle est affichée pour ne rien cacher, pas pour être lue.

### La topologie du graphe pèse aussi, mais ce n'est pas encore établi

Sur le seul jeu où les quatre topologies coexistent :

| topologie | n | réparés | IC 95 % | recouvr. méd. | morceaux méd. |
|---|--:|--:|:--:|--:|--:|
| `plausible` | 24 | 75,0 % | [55,1–88,0] | 0,93 | 3 |
| `etoile` | 28 | 64,3 % | [45,8–79,3] | 0,93 | 4 |
| `anneau` | 24 | 54,2 % | [35,1–72,1] | 1,00 | 3 |
| `chaine` | 24 | 41,7 % | [24,5–61,2] | **1,42** | 2 |

L'ordre suit le nombre d'arêtes du graphe, et le mécanisme est clair : seules les pièces
reliées s'attirent de l'attention, donc plus le graphe est pauvre, plus les pièces se
superposent — la chaîne, qui a le minimum d'arêtes, a bien le pire taux de recouvrement
(1,42 contre 0,93).

**Ce n'est pas concluant** : à n = 24 par cellule, les intervalles de `chaine` et
`plausible` se frôlent sans se séparer nettement. Ce n'est en revanche pas un effet de
taille : `chaine` porte les programmes les **plus petits** (5,67 pièces en moyenne
contre 6,17 pour `anneau`) et obtient le **pire** taux.

### Les échecs restants sont nommés, et 13 sont prouvés

À budget 16, il reste 112 à 116 refus de trame — la réparation bornée n'y suffit pas —
et **13 infaisabilités certifiées**. Ce ne sont pas des plantages : le certificat de
Farkas est un vecteur creux de 2 à 3 composantes non nulles sur 45, et les origines
nomment le conflit minimal, par exemple `separation horizontale p000|p003 ; contour
droit p000`. À grand budget, la trame réparée finit par contredire les séparations
issues de `deduire_ordre` — ce qui explique aussi la saturation observée.

## Ce que ce jalon établit, et ce qu'il ne prétend pas

Il établit que la contrainte de pavage est **nécessaire** : sur 740 plans générés sous
trois conditionnements, **aucun** n'est récupérable sans elle, environ un sur cinq l'est
avec. L'écart n'est pas un effet de réglage.

Il établit aussi qu'elle n'est **pas suffisante**, et de deux façons.

D'abord, le déplacement médian atteint 38 à 43 % du côté du plan : ce qui sort est un
plan valide *au voisinage* du plan généré, pas le plan généré corrigé. Quand l'entrée
est aussi loin de tout pavage exact, « le plan valide le plus proche » n'est pas proche
— la projection L1 fait son travail, c'est l'entrée qui est pathologique. Le point de
comparaison est le budget 0, où les rares plans déjà presque cohérents ne se déplacent
que de 18 %.

Ensuite, **quatre plans sur cinq ne sont pas réparables du tout** en préservant le
programme. Le chiffre de ~60 % qu'on obtient sans plancher sur la largeur n'en est pas
un : il compte comme succès des plans amputés d'une pièce.

La conclusion utile n'est donc pas « on répare 61 % », ni même « on répare 20 % », mais :
**la légalisation a posteriori ne remplace pas un générateur qui respecte la condition
de pavage**. Elle garantit la validité et la prouve ; elle ne garantit ni la
ressemblance ni la survie du programme, et il faut le lui demander explicitement. La
contrainte a sa place *dans* le générateur — ce que ce dépôt permet de chiffrer, pas ce
qu'il fournit.

Cela confirme le jalon 7 comme table principale : c'est lui qui isole la capacité de
réparation dans le régime où réparer a un sens, avec une faute connue et attribuable.

## Reproduire

L'échantillonnage vit **hors du dépôt** : HouseDiffusion est sous GPL v3 et interdit
d'usage commercial, archlux est sous Apache-2.0 et ne l'importe pas. La frontière entre
les deux est le fichier JSONL.

```bash
# etage 1, hors depot (GPL)
python vendor/j8_generer.py plans.jsonl --n 40 --pas 1000 --graphe plausible
python vendor/j8_generer.py divers.jsonl --n 4  --pas 1000 --catalogue divers

# etage 2, dans le depot (Apache-2.0) : tables, puis fiches avant/apres
python experiences/j8_generation.py plans.jsonl 999 plausible
python experiences/j8_visuels.py    plans.jsonl plausible 8
```

Le lot d'echantillonnage est **heterogene** — un programme par element — parce que le
cout est domine par les 1000 pas sequentiels et non par la taille du lot : tout le
catalogue *divers* tient en un passage de quatre minutes plutot que vingt-cinq de
trois.
