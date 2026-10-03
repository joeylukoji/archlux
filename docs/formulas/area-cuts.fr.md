# Coupes de surface

**Code :** `lmo.cuts.area_cut`, `violated_areas`, `solve_with_areas`.

## Énoncé

La contrainte réglementaire \(w h \ge a_{\min}\) n'est **pas** une inégalité
linéaire. Sur \(\mathbb{R}_{>0}^2\), posons \(g(w,h)=\log w+\log h\). \(g\) est
concave (Boyd & Vandenberghe, 2004, §3.1.5). Ses super-niveaux

\[
K=\bigl\{(w,h):w>0,\; h>0,\; wh\ge a_{\min}\bigr\}
 =\bigl\{ g \ge \log a_{\min}\bigr\}
\]

sont donc **convexes** (ibid., §3.1.6).

Au point de contact \((w_0,h_0)\) de l'hyperbole \(w_0 h_0=a_{\min}\),
\(\nabla g=(1/w_0,\,1/h_0)\) et le demi-espace d'appui contenant \(K\) s'écrit

\[
\frac{w-w_0}{w_0}+\frac{h-h_0}{h_0}\ge 0
\quad\Longleftrightarrow\quad
h_0 w + w_0 h \ge 2 a_{\min}.
\]

## Dérivation — gradient

Multiplier \(\nabla g\cdot\bigl((w,h)-(w_0,h_0)\bigr)\ge 0\) par \(w_0 h_0>0\) :

\[
h_0(w-w_0)+w_0(h-h_0)\ge 0
\implies
h_0 w + w_0 h \ge 2 w_0 h_0 = 2 a_{\min}.
\]

## Dérivation — AM-GM (même inégalité)

Hardy, Littlewood & Pólya (1952), théorème 16 :

\[
\frac{1}{2}\Bigl(\frac{w}{w_0}+\frac{h}{h_0}\Bigr)
 \ge \sqrt{\frac{wh}{w_0 h_0}}.
\]

Sur l'hyperbole \(w_0 h_0=a_{\min}\), le membre de droite vaut au moins \(1\) dès
que \(wh\ge a_{\min}\), d'où \(h_0 w+w_0 h\ge 2 a_{\min}\). **Aucun** point de
\(K\) n'est exclu. Un point de produit strictement inférieur peut l'être.

## Projection avant la tangente

Si le point courant viole \(wh<a_{\min}\), la tangente écrite *là* passe par un
point **intérieur au complémentaire** de \(K\). Elle coupe alors l'hyperbole et
exclut des rectangles admissibles de même rapport d'aspect.

On projette d'abord sur l'hyperbole en conservant le rapport :

\[
(w_\star,h_\star)
 =\sqrt{\frac{a_{\min}}{wh}}\,(w,h).
\]

C'est le code de `area_cut`.

## Pourquoi Kelley seul oscille

Le simplexe ne rend que des **sommets** d'un polyèdre. \(K\) a un bord
strictement convexe : l'optimum de \(\min(w+h)\) sur \(K\) est le carré
\((\sqrt{a},\sqrt{a})\) (AM-GM), qui n'est un sommet d'aucune approximation
finie. Les sommets glissent sur une corde \(w+h=2\sqrt{a}\), produit
\(a-\delta^2\).

Kelley (1960) densifie les tangentes. En complément, on **resserre les bornes**
\(w\ge w_\star\), \(h\ge h_\star\) (intersection hyperbole–boîte si le rayon sort)
puis on relance GLOP, qui réajuste \(x,y\). Si ce resserrement rend le LP
infaisable (mauvais rapport d'aspect), on **l'abandonne** et on continue les
coupes — on ne déclare pas le programme infaisable.

Tangentes initiales : le carré et les intersections de l'hyperbole avec
\(w=w_{\min}\), \(h=h_{\min}\), si elles tiennent dans la boîte des bornes.

`MAX_CUTS_PER_ROOM = 10` : au-delà, `log.warning("coupe.limite", piece=...)`.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Appeler `solve_with_areas` depuis `legalize` (le référentiel connaît \(a_{\min}\)) | Mettre la boucle dans `lmo.solver.solve` — `lmo` ignore l'origine de \(c\) **et** le programme |
| Projeter avant d'écrire la coupe | Passer \(wh\ge a\) à GLOP comme produit |
| Laisser `a_min=0` sans coupe | Croire qu'après 10 coupes le sommet LP est *sur* l'hyperbole : d'où le resserrement de bornes |

## Approximation intérieure, pour Frank-Wolfe

Les coupes tangentes sont une approximation **extérieure** de
\(K = \{(w, h) : wh \ge a\}\) : la légalisation classique les utilise, puis vérifie le
résultat exactement. Frank-Wolfe ne le peut pas : ses itérés sont des combinaisons
convexes d'un départ valide et de sommets du PL, et un sommet d'une approximation
extérieure peut se trouver sous l'hyperbole, si bien que le mélange peut violer la
surface minimale. C'est ce qui se produisait jusqu'à 0.10 (AUDIT.md §3 n°6).

Frank-Wolfe travaille donc sur une approximation **intérieure**
(`lmo.cuts.inner_area_constraints`). Autour du départ \((w_0, h_0)\), on prend les nœuds
\(w_k = f_k w_0\), \(f_k = 1.1^k\) pour \(k = -24, \dots, 24\) (environ 0,10 à 9,85), et
\(h_k = a / w_k\). Les nœuds ne sont pas filtrés par les bornes des variables (la région
est de toute façon intersectée avec elles) : le filtrage figeait les pièces dont un
contact avait fixé la hauteur. On garde

\[
w \ge w_{\text{first}}, \qquad h \ge \frac{a}{w_{\text{last}}}, \qquad
h \ge h_k + s_k (w - w_k) \quad \text{for each chord } [w_k, w_{k+1}],
\quad s_k = \frac{h_{k+1} - h_k}{w_{k+1} - w_k}.
\]

**Correction.** \(h = a/w\) est convexe sur \(w > 0\), donc elle se trouve sous chacune
de ses cordes : sur \([w_{\text{first}}, w_{\text{last}}]\), l'interpolant affine par
morceaux \(\ell\) vérifie \(\ell(w) \ge a/w\). \(\ell\) est convexe (interpolant d'une
fonction convexe), donc égal au maximum de ses cordes prolongées : les lignes de cordes
décrivent exactement son épigraphe. Au-delà de \(w_{\text{last}}\),
\(h \ge a/w_{\text{last}} > a/w\). La région conservée est un polyèdre convexe inclus
dans \(K\) : tout point du domaine, et toute combinaison convexe de tels points,
respecte la surface minimale.

**Le départ reste admissible**, puisque \(w_0\) est un nœud : les lignes exigent
seulement \(h_0 \ge a/w_0\).

**Coût de l'approximation.** Entre deux nœuds de rapport \(r = w_{k+1}/w_k\), la corde
demande au plus \(\frac{(r-1)^2}{4r}\) de surface en plus du minimum (maximum de
\(w\,\ell(w)/a - 1\), atteint au milieu \((w_k + w_{k+1})/2\) des nœuds). Avec
\(r = 1.1\) partout, c'est un +0,23 % uniforme. L'autre prix est l'étendue : la largeur
d'une pièce reste entre environ 0,10 et 9,85 fois celle du départ.

Effet mesuré sur l'optimisation, 200 scénarios du banc, contre une grille de référence de
235 nœuds (rapport 1,02) : la grille par défaut atteint une médiane de 0,9985 du gain de
référence, et au moins 0,95 de celui-ci dans 96 % des scénarios, pour +4 ms médianes par
appel. Une grille plus grossière (rapport 1,25, 13 nœuds) n'atteignait 0,95 que dans
81 % d'entre eux. Les cas aberrants restants ne décroissent pas de façon monotone avec
des grilles plus fines : ils viennent du chemin que Frank-Wolfe suit sur un objectif non
concave, pas de l'approximation.

Un unique coin \(w \ge w_0, h \ge h_0\) aurait aussi été correct, mais il fige la forme
d'une pièce dont la surface est serrée ; les cordes lui permettent d'échanger de la
largeur contre de la hauteur.

Comme Frank-Wolfe n'a plus besoin des coupes tangentes, ses appels au PL gardent le
démarrage à chaud (les coupes le désactivaient, AUDIT.md Q-C2).

## Source

- Boyd & Vandenberghe (2004), §3.1.5–3.1.6.
- Hardy, Littlewood & Pólya (1952), th. 16.
- Kelley (1960), *SIAM J.*, [doi:10.1137/0108053](https://doi.org/10.1137/0108053).

[Bibliographie](sources.md).
