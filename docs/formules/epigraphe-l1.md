# Épigraphe de la distance L1

**Code :** `geom.polytope.etendre_ecarts_l1`, `api.gradient_distance`.

## Énoncé

On veut le plan valide *le plus proche* du plan proposé \(\hat x\in\mathbb{R}^n\),
au sens

\[
\min_x \lVert x-\hat x\rVert_1 = \min_x \sum_{i=1}^n \lvert x_i-\hat x_i\rvert,
\]

sous \(x\) dans le [polytope](polytope-separe.md). La valeur absolue n'est pas
linéaire. L'**épigraphe** (Bertsimas & Tsitsiklis, 1997, §1.3) introduit
\(e_i\ge 0\) tel que

\[
e_i \ge x_i-\hat x_i, \qquad e_i \ge \hat x_i-x_i,
\]

équivalent, sous la forme \(Ax\le b\) du projet, à

\[
x_i - e_i \le \hat x_i, \qquad -x_i - e_i \le -\hat x_i.
\]

L'objectif devient linéaire :

\[
\min\; \sum_{i=1}^n e_i = \min\; c^\top (x,e),
\qquad
c=(0,\ldots,0,1,\ldots,1)\in\mathbb{R}^{2n}.
\]

Les \(\hat x_i\) sont dans les **contraintes**, jamais dans \(c\).
`gradient_distance` ne lit de \(\hat x\) que sa dimension \(n\).

## Hypothèses

- Colonnes \(0..n-1\) inchangées (variables géométriques) ; écarts en \(n..2n-1\),
  nommés `e.<variable>`.
- Les deux familles d'inégalités sont **obligatoires**. En omettre une rend \(e_i\)
  libre d'un côté : le déplacement apparent explose (`MILESTONE-2.md` §10).
- Si \(\hat x\) est déjà admissible, l'optimum est \(e=0\), \(x^\star=\hat x\).

## Dérivation

Pour \(t\in\mathbb{R}\), \(\lvert t\rvert = \min\{ e : e\ge t,\; e\ge -t\}\).
Poser \(t=x_i-\hat x_i\). Sommer les \(e_i\) et rester dans le polytope agrandi.

Les bornes des \(e_i\) sont \((0,+\infty)\), traduites en `solver.infinity()` pour
GLOP (un `float('inf')` Python n'est pas une borne GLOP).

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Légalisation classique (`objective is None`) | Mettre \(\hat x\) dans \(c\) (l'objectif cesserait d'être la somme des écarts) |
| Plafonner chaque \(e_i\) par `budget=` | Croire que L1 *remplit* l'enveloppe : les séparations sont des inégalités, un plan troué reste proche de lui-même. Les [jours](preuve-exacte.md) ne sont garantis que si l'entrée est déjà un pavage (ou un chevauchement dont l'union couvre le contour) |
| Relire `e.<nom>` dans `index` | Vectoriser un plan avec l'index *étendu* (les clés `e.*` ne sont pas des pièces) |

## Source

Bertsimas & Tsitsiklis (1997), §1.3 — formulation LP des valeurs absolues.
[Bibliographie](sources.md).
