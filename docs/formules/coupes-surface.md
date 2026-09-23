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

## Source

- Boyd & Vandenberghe (2004), §3.1.5–3.1.6.
- Hardy, Littlewood & Pólya (1952), th. 16.
- Kelley (1960), *SIAM J.*, [doi:10.1137/0108053](https://doi.org/10.1137/0108053).

[Bibliographie](sources.md).
