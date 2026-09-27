# Jalon 7 — ou est la variance de l'irradiance ?

Corpus Swiss Dwellings v3.0.0, 367 466 pieces, cible `sun_201803211200_mean`.
Variance totale 17,89.

| effet fixe | groupes | R2 |
|---|--:|--:|
| identite du batiment | 3 171 | **0,026** |
| batiment x etage | 13 688 | 0,068 |
| identite de l appartement | 44 888 | **0,077** |
| numero d etage seul | — | 0,004 |

## Lecture

**92 % de la variance est intra-appartement**, c'est-a-dire entre pieces. L'identite
du batiment — qui porte le masque urbain, le climat et la position solaire — n'explique
que **2,6 %**.

Deux consequences, et la seconde est structurelle.

**Le masque urbain n'est pas le facteur manquant.** L'hypothese etait naturelle et elle
est fausse : un effet de batiment plafonne a 2,6 %. Les normales climatiques le
confirment par un autre chemin — `climate_snorm_year` correle a r = -0,06 avec la
cible, `climate_snorm_march` a r = +0,05. `sun_*` est un lancer de rayons geometrique
a position solaire donnee, pas une grandeur meteo.

**Agreger par appartement detruit le signal.** Le protocole `Substitut` rend **un
scalaire par plan** ; l'eclairement est une grandeur **par piece**. Predire une moyenne
d'appartement revient a predire une quantite dont la variance ne represente que 7,7 %
de celle du phenomene, le reste etant lisse par l'agregation. C'est ce qui explique les
`R2 ~ 0` de `j7_sd_etiquettes.md` bien plus que la pauvrete des entrees.

## Ce que cela implique

La granularite du protocole est en cause, pas seulement son vocabulaire. Un substitut
utile rendrait un **vecteur** — une valeur par piece — et Frank-Wolfe optimiserait une
scalarisation explicite de ces valeurs (moyenne ponderee, minimum, part au-dessus d'un
seuil). C'est aussi ce qui rendrait un indicateur de type sDA representable : il se
definit par piece, pas par logement.

C'est un changement de contrat plus profond que l'ajout des `Baies`, et il touche
`solve` autant que `light`.
