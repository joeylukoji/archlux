
# Polytope des séparations

**Code :** `geom.polytope.construire_polytope`, `Polytope.contient`, `vectoriser`,
`devectoriser`.

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
**`bornes`**, pas par \(A\) : \(w_i,h_i\in[\ell_{\min}, L]\) où \(L\) est le côté
de l'enveloppe.

L'ensemble \(\{x : Ax\le b,\; \ell\le x\le u\}\) est un **polyèdre** (Boyd &
Vandenberghe, 2004, §2.2.4).

## Hypothèses

- Ordre relatif fixé (sinon le domaine des plans valides n'est **pas** convexe :
  on peut contourner \(B\) par deux chemins dont le segment n'est pas admissible).
- Graphe réduit transitivement *avant* l'assemblage.
- Load-bearing walls are fixed obstacles. Each room keeps the side of each wall it
  had in the proposed plan (`OrdreRelatif.porteurs`): one inequality per room and
  wall, \(x + w \le c\) (left), \(x \ge c\) (right), \(y + h \le c\) (below) or
  \(y \ge c\) (above), where \(c\) is the wall line or the end of a partial wall. A
  room that crosses a wall is sent to the side of its centre. Oblique load-bearing
  walls are refused (`UnsupportedInput`). \(A_{\mathrm{eq}}\) stays empty.

## Ce qui n'est pas dans \(A\)

\(w h \ge a_{\min}\) n'est pas linéaire. La reporter aux
[coupes de surface](coupes-surface.md). L'écrire telle quelle dans GLOP est une
erreur de modèle, pas un détail d'implémentation.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| `contient(x)` comme oracle **indépendant** du solveur | Faire confiance à `statut == "optimal"` sans `contient` ni `verifier_exactement` |
| Garder `origines[i]` = libellé de la ligne \(i\) de \(A\) | Numéroter les duaux par indice de ligne nu |
| Vectoriser / dévectoriser via `index` | Stocker une baie en coordonnées absolues (elle se désynchronise du mur) |

`Polytope.contient` est volontairement naïf : \(Ax \le b+\varepsilon\), égalités,
bornes. C'est lui qui attrape un bogue du simplexe.

## Source

- Boyd & Vandenberghe (2004), §2.2.4 — polyèdres.
- Lengauer (1990), ch. 10 — compaction.
- Otten (1982) — plans en guillotine, qui sont des points de ce polytope.

[Bibliographie](sources.md).
