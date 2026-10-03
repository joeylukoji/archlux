
# Polytope des séparations

**Code :** `geom.polytope.build_polytope`, `Polytope.contains`, `vectorize`,
`devectorize`.

## Énoncé

Quatre variables par pièce, dans cet ordre : \(x,y,w,h\). L'index
`"<id>.x"` est un contrat : une trace de duaux n'est relisible que si les colonnes
ne bougent pas.

Pour chaque arête horizontale \(a\to b\) du graphe *réduit* :

\[
x_a + w_a - x_b \le 0.
\]

Verticalement : \(y_a + h_a - y_b \le 0\). L'enveloppe rectangulaire
\([x_{\min},x_{\max}]\times[y_{\min},y_{\max}]\) ajoute

\[
x_i + w_i \le x_{\max},\qquad y_i + h_i \le y_{\max}.
\]

Les bords bas / gauche et les largeurs minimales \(\ell_{\min}\) passent par
**`bounds`**, pas par \(A\) : \(w_i,h_i\in[\ell_{\min}, L]\) où \(L\) est le côté
de l'enveloppe.

L'ensemble \(\{x : Ax\le b,\; \ell\le x\le u\}\) est un **polyèdre** (Boyd &
Vandenberghe, 2004, §2.2.4).

## Hypothèses

- Ordre relatif fixé (sinon le domaine des plans valides n'est **pas** convexe :
  on peut contourner \(B\) par deux chemins dont le segment n'est pas admissible).
- Graphe réduit transitivement *avant* l'assemblage.
- Les murs porteurs sont des obstacles fixes. Chaque pièce garde le côté de chaque mur
  qu'elle avait dans le plan proposé (`RelativeOrder.wall_sides`) : une inégalité par
  pièce et par mur, \(x + w \le c\) (à gauche), \(x \ge c\) (à droite), \(y + h \le c\)
  (en dessous) ou \(y \ge c\) (au-dessus), où \(c\) est la ligne du mur ou l'extrémité
  d'un mur partiel. Le demi-plan conservé est celui où la pièce proposée pénètre **le
  moins**, parmi ceux qui laissent de la place avant le contour : pour une pièce à
  l'écart du mur, c'est l'axe du plus grand écart (la règle entre deux pièces) ; pour
  une pièce qui le traverse, la plus petite correction, qui peut contourner l'extrémité
  d'un mur partiel. Les murs de longueur nulle sont ignorés ; les murs porteurs obliques
  sont refusés (`UnsupportedInput`). \(A_{\mathrm{eq}}\) reste vide.
- **Surcontrainte délibérée.** Une pièce au-delà de l'extrémité d'un mur partiel
  pourrait aussi en être tenue à l'écart par un autre demi-plan ; un seul est conservé,
  donc Frank-Wolfe ne peut pas faire passer la pièce d'un côté valide à un autre. C'est
  le prix de la convexité, exactement comme pour l'ordre relatif entre deux pièces :
  sûr, jamais un faux certificat, mais cela restreint la recherche.

## Ce qui n'est pas dans \(A\)

\(w h \ge a_{\min}\) n'est pas linéaire. La reporter aux
[coupes de surface](area-cuts.md). L'écrire telle quelle dans GLOP est une
erreur de modèle, pas un détail d'implémentation.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| `contains(x)` comme oracle **indépendant** du solveur | Faire confiance à `status == "optimal"` sans `contains` ni `verify_exactly` |
| Garder `origins[i]` = libellé de la ligne \(i\) de \(A\) | Numéroter les duaux par indice de ligne nu |
| Vectoriser / dévectoriser via `index` | Stocker une baie en coordonnées absolues (elle se désynchronise du mur) |

`Polytope.contains` est volontairement naïf : \(Ax \le b+\varepsilon\), égalités,
bornes. C'est lui qui attrape un bogue du simplexe.

## Source

- Boyd & Vandenberghe (2004), §2.2.4 — polyèdres.
- Lengauer (1990), ch. 10 — compaction.
- Otten (1982) — plans en guillotine, qui sont des points de ce polytope.

[Bibliographie](sources.md).
