# Coupes de surface

**Code :** `lmo.coupes.coupe_surface`, `surfaces_violees`, `resoudre_avec_surfaces`.

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

C'est le code de `coupe_surface`.

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

`MAX_COUPES_PAR_PIECE = 10` : au-delà, `log.warning("coupe.limite", piece=...)`.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Appeler `resoudre_avec_surfaces` depuis `legalize` (le référentiel connaît \(a_{\min}\)) | Mettre la boucle dans `lmo.solveur.resoudre` — `lmo` ignore l'origine de \(c\) **et** le programme |
| Projeter avant d'écrire la coupe | Passer \(wh\ge a\) à GLOP comme produit |
| Laisser `a_min=0` sans coupe | Croire qu'après 10 coupes le sommet LP est *sur* l'hyperbole : d'où le resserrement de bornes |

## Inner approximation, for Frank-Wolfe

Tangent cuts are an **outer** approximation of \(K = \{(w, h) : wh \ge a\}\): the
classic legalization uses them, then checks the result exactly. Frank-Wolfe cannot:
its iterates are convex combinations of a valid start and LP vertices, and a vertex of
an outer approximation may lie below the hyperbola, so the mix can break the minimum
area. That is what happened until 0.10 (AUDIT.md §3 n°6).

Frank-Wolfe therefore works on an **inner** approximation
(`lmo.coupes.inner_area_constraints`). Around the start \((w_0, h_0)\), take nodes
\(w_k = f_k w_0\), \(f_k = 1.25^k\) for \(k = -6, \dots, 6\) (about 0.26 to 3.8), and
\(h_k = a / w_k\). Nodes are not filtered by the variable bounds (the region is
intersected with them anyway): filtering froze rooms whose height a contact had fixed.
Keep

\[
w \ge w_{\text{first}}, \qquad h \ge \frac{a}{w_{\text{last}}}, \qquad
h \ge h_k + s_k (w - w_k) \quad \text{for each chord } [w_k, w_{k+1}],
\quad s_k = \frac{h_{k+1} - h_k}{w_{k+1} - w_k}.
\]

**Soundness.** \(h = a/w\) is convex on \(w > 0\), so it lies below each of its chords:
on \([w_{\text{first}}, w_{\text{last}}]\) the piecewise-linear interpolant \(\ell\)
satisfies \(\ell(w) \ge a/w\). \(\ell\) is convex (interpolant of a convex function),
hence equal to the maximum of its extended chords, so the chord rows describe exactly
its epigraph. Beyond \(w_{\text{last}}\), \(h \ge a/w_{\text{last}} > a/w\). The kept
region is a convex polyhedron included in \(K\): every point of the domain, and every
convex combination of such points, keeps the minimum area.

**The start stays admissible**, since \(w_0\) is a node: the rows only require
\(h_0 \ge a/w_0\).

**Cost of the approximation.** Between two nodes of ratio \(r = w_{k+1}/w_k\), the
chord asks for at most \(\frac{(r-1)^2}{4r}\) more area than the minimum (maximum of
\(w\,\ell(w)/a - 1\), reached at the midpoint \((w_k + w_{k+1})/2\) of the nodes). With
\(r = 1.25\) everywhere this is a uniform +1.25 %, checked numerically. This is the
price of keeping the domain linear; the other price is the spread, since a room cannot
change its aspect ratio by more than about 15. A single corner \(w \ge w_0, h \ge h_0\) would have been
sound too, but it freezes the shape of a room whose area is tight; the chords let it
trade width for height within the spread.

Since Frank-Wolfe no longer needs tangent cuts, its LP calls keep the warm start
(the cuts used to disable it, AUDIT.md Q-C2).

## Source

- Boyd & Vandenberghe (2004), §3.1.5–3.1.6.
- Hardy, Littlewood & Pólya (1952), th. 16.
- Kelley (1960), *SIAM J.*, [doi:10.1137/0108053](https://doi.org/10.1137/0108053).

[Bibliographie](sources.md).
