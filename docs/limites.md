# Limites

**À lire avant tout usage professionnel.** Cette page est obligatoire, pas optionnelle :
un outil qui produit des chiffres réglementaires doit dire explicitement ce qu'il ne
vérifie pas.

## Estimations de phase amont

Les indicateurs produits sont des **estimations de phase amont**. Ils ne se substituent
pas à une étude thermique ou d'éclairement réglementaire. La borne du jalon 5 couvre
l'oracle gelé (`SplitFluxOracle` split-flux / analytique), **pas** un sDA LM-83
(Radiance). Extra `sim` : vide volontairement.

## Sur une sortie de générateur, le plan valide le plus proche n'est pas proche

**C'est la limite qui décide de l'usage réel du légaliseur, et elle est mesurée.**

Le jalon 7 répare 93,9 % de plans MSD **corrompus à la main**, en déplaçant peu. Le
jalon 8 refait la mesure sur des plans **réellement générés** — HouseDiffusion (CVPR
2023), poids officiels, 1000 pas, 740 plans sous trois conditionnements. Le régime n'est
pas le même :

| sur les sorties du générateur | médiane |
|---|--:|
| plans valides avant correction | **0 / 740** |
| pièces recouvertes par pièce | 0,80 |
| part de jour dans l'enveloppe | 28,6 % |
| morceaux disjoints de l'union | **4** |
| cellules de la trame implicite (6 pièces) | **80** |

Un plan corrompu est un plan valide dont une cote a bougé : sa trame existe, il suffit
de la retrouver. Une sortie de générateur n'a **pas de trame** — ses pièces ne partagent
presque aucune ligne, l'union tombe en quatre morceaux, et la structure combinatoire
que `geom.pavage` exploite n'est pas seulement violée, elle est absente.

Conséquences chiffrées, à budget de réparation 16 et `largeur_min = 0,50 m` :

- `legalize` seul répare **0,0 %** — attendu : un jour est un point stationnaire de
  l'optimum L1, exactement ce que `pavage` existe pour corriger ;
- `legalize(pavage=True)` répare **17,8 à 23,0 %** selon le conditionnement, en
  déplaçant de **38 à 43 % du côté** du plan. Le résultat est un plan valide *au
  voisinage* du plan généré, pas le plan généré corrigé ;
- **sans plancher sur la largeur, ce taux monte à ~60 % — et c'est un trompe-l'œil.**
  Fermer un jour en réduisant une pièce à zéro est la solution la moins coûteuse : 61 %
  des plans alors réputés réparés portaient au moins une pièce de côté **exactement
  nul**, et sortaient certifiés valides, amputés. Compter les pièces ne le détecte pas.
  Le taux est **plat de 0,25 m à 1,80 m** : ce n'est pas un calibrage de seuil mais un
  choix binaire, autoriser ou non les solutions dégénérées ;
- le taux chute avec la taille du programme, parce que la trame enfle en
  \\((2n-1)^2\\) quand aucun bord ne coïncide, alors que la réparation bornée ne
  corrige qu'un nombre borné de cellules ;
- des plans sont **prouvés infaisables** : la trame réparée contredit alors les
  séparations issues de `deduire_ordre`, et le certificat de Farkas nomme le conflit
  minimal (2 à 3 lignes sur 45).

Ce que cela veut dire pour un utilisateur : **la légalisation a posteriori ne remplace
pas un générateur qui respecte la condition de pavage.** Elle garantit la validité et
la prouve ; elle ne garantit ni la ressemblance ni la survie du programme, et il faut
lui demander cette dernière explicitement, par un `largeur_min` strictement positif. La
contrainte a sa place *dans* le générateur — ce que ce dépôt permet de chiffrer, pas ce
qu'il fournit.

Détail, protocole et comparaisons avant / après plan par plan :
`resultats/j8_generation.md` et `resultats/visuels/`.

## Le substitut prédit à la mauvaise granularité

**C'est la limite la plus profonde du projet, et elle est mesurée.**

Le protocole `Substitut` rend **un scalaire par plan**. L'éclairement est une grandeur
**par pièce**. Décomposition de la variance sur 367 466 pièces de Swiss Dwellings,
cible `sun_201803211200_mean` :

| effet fixe | groupes | \(R^2\) |
|---|--:|--:|
| identité du bâtiment | 3 171 | **0,026** |
| bâtiment × étage | 13 688 | 0,068 |
| identité de l'appartement | 44 888 | **0,077** |
| numéro d'étage seul | — | 0,004 |

**92 % de la variance est intra-appartement**, entre pièces. Agréger en moyenne de
logement revient donc à prédire une quantité dont la variance ne pèse que 7,7 % du
phénomène : le reste est lissé par l'agrégation elle-même.

C'est ce qui explique les \(R^2 \approx 0\) mesurés — analytique \(-0{,}000\),
perceptron \(-0{,}557\), perceptron avec baies \(-0{,}220\) — bien plus que la
pauvreté des entrées. Enrichir l'entrée aide réellement (les baies comblent 60 % de
l'écart) mais s'attaque au mauvais problème.

Conséquence pratique : **aucun indicateur de type sDA n'est représentable** par ce
protocole. Le sDA se définit par pièce — part du sol au-dessus de 300 lux — jamais par
logement. Un substitut utile rendrait un vecteur, une valeur par pièce, et Frank-Wolfe
optimiserait une scalarisation explicite de ces valeurs.

## Le masque urbain n'est pas le facteur manquant

L'hypothèse était naturelle, et deux vérifications indépendantes la réfutent.

L'identité du bâtiment — qui porte le masque urbain, le climat et la position solaire —
n'explique que **2,6 %** de la variance. Et les normales climatiques ne corrèlent pas :
`climate_snorm_year` donne \(r = -0{,}06\), `climate_snorm_march` \(r = +0{,}05\).
La cible est un lancer de rayons **géométrique** à position solaire fixée, pas une
grandeur météorologique.

Aucune géométrie d'environnement bâti n'est d'ailleurs publiée dans le corpus : le
masque n'existe que dans les sorties de simulation. S'en servir comme entrée exigerait
de simuler pour prédire, ce qui vide le substitut de sa raison d'être.

Détail et protocole : `resultats/j7_variance.md`.

## Le substitut appris n'a jamais vu de mesure

Les étiquettes **livrées dans ce dépôt** viennent de
`light.simulateur.SplitFluxOracle`, une **forme fermée** (analytique CIBSE +
split-flux BRE). Le perceptron `light.base.SubstitutDense` y apprend le *résidu* entre
cette forme fermée et `SubstitutAnalytique` : deux formules connues, sur 90 pavages
2×2 à deux degrés de liberté, sans murs ni ouvertures.

Des étiquettes réelles sont désormais atteignables — `data.chargeurs` joint MSD aux
simulations Swiss Dwellings, 18 263 appartements sur 18 270 — mais elles ne sont pas
redistribuées, et la mesure faite contre elles est un **résultat négatif** : voir
ci-dessus.

Autrement dit : la chaîne tokenisation → entraînement → gel → calibration conforme →
Frank-Wolfe est **exercée de bout en bout**, et aucune grandeur physique n'a été
mesurée. Le transformeur annoncé au jalon 4 n'existe pas — `SubstitutAppris` refuse
les poids `.pt`.

Toute couverture rapportée par ce dépôt est donc une couverture **sur l'oracle gelé**,
jamais sur un éclairement observé. Les sources d'étiquettes réelles et leur coût sont
détaillées dans [vérité terrain](donnees/verite-terrain.md).

## Échangeabilité et sélection

La garantie de performance suppose l'**échangeabilité** avec le jeu de calibration.
Les plans produits par un optimiseur sont *sélectionnés* pour maximiser la
prédiction : la couverture réelle sous cette sélection est une question de
recherche ouverte, mesurée et publiée par le projet (dérive, banc d'essai).
Le certificat le dit : la borne d'un plan rendu par `legalize` porte
`regime="selected"`, et le rapport écrit « couverture NON garantie » au lieu d'un
pourcentage. Pour un plan échangeable, si la dérive est détectée, le certificat
affiche `NON EVALUABLE` plutôt qu'un intervalle trompeur.

## Load-bearing structure: what is and is not certified

Since 0.10 (ADR-7), the certificate proves that **no room crosses a load-bearing wall**,
and the solver keeps every room on its side of each wall. It does not certify more:

- **Columns** (`Structure.poteaux`) are not constrained or checked: a column inside a
  room is normal in housing, and nothing is claimed about them.
- **Openings on interior partitions do not follow a moved room**: walls are not decision
  variables. Openings on facades stay put because the outline is fixed.
- **Oblique load-bearing walls are refused** (`UnsupportedInput`) rather than ignored:
  no linear side constraint keeps a rectangle off an oblique segment exactly.
- Each room keeps **one** side of each wall, read from the proposed plan: a valid
  arrangement on another side of a partial wall is not explored.

## `NON EVALUABLE`

Le champ **`NON EVALUABLE`** couvre les articles dont la vérification exige une
information absente du plan — matériaux, systèmes techniques, confort d'été —
ou une interprétation réglementaire. Ce n'est pas un oubli de calcul : c'est un
refus explicite d'inventer une couverture.

## Pas un avis juridique

La vérification calcule des prédicats sur une géométrie (et, le cas échéant,
une borne probabiliste sur un oracle gelé). **Elle ne constitue pas un avis
juridique** ni une attestation de conformité administrative.

## Ce que la vérification automatique ne peut pas établir

- Que le plan est constructible au sens du chantier (tolérances, phasage, fluides).
- Que les ouvertures imputées (si corpus lacunaire) correspondent au bâtiment réel.
- Qu'un export IFC « valide » au sens des pathologies `archlux` est accepté par
  tout outil BIM tiers sans retraitement.
- Qu'une couverture conforme à 90 % sur l'oracle gelé vaut pour un autre climat,
  un autre usage, ou un autre générateur hors distribution de calibration.

> Un plan produit par ce système est une proposition, jamais un document de projet.

API **non gelée** : version de développement `0.10.0.dev0`, la 1.0.0 est reportée à la fin de la phase 5 de `PLAN.md` ; checklist hors code :
[publication 1.0](publication-1.0.md).

**Voir aussi :** [Les deux garanties](concepts/deux-garanties.md),
[Contribuer](contribution.md).
