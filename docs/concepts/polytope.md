# Le polytope des plans valides

Un ordre relatif fixé (A à gauche de B, C sous D) transforme la légalisation en
**programme linéaire**. Sans cet ordre, le domaine des plans valides n'est pas convexe :
on peut glisser A autour de B par deux chemins dont le segment n'est pas admissible.

## Formule

Quatre variables par pièce : `(x, y, w, h)`. Pour chaque arête horizontale `a → b`
du graphe d'ordre (Otten, *Automatic Floorplan Design*, DAC 1982, pavages en
guillotine ; compaction par graphe de contraintes, Lengauer, *Combinatorial Algorithms
for Integrated Circuit Layout*, Teubner, 1990, ch. 10) :

```
x_a + w_a ≤ x_b
```

Idem à la verticale : `y_a + h_a ≤ y_b`. L'enveloppe ajoute `x + w ≤ X_max` et
`y + h ≤ Y_max`. Les largeurs minimales sont des bornes, pas des lignes de `A`.

L'ensemble des `x` qui satisfont `A x ≤ b` est un **polyèdre** (Boyd & Vandenberghe,
*Convex Optimization*, Cambridge University Press, 2004, §2.2.4). Tout point de ce
polyèdre est un plan sans chevauchement, à ordre relatif fixé.

## Ce qui n'est pas linéaire

La surface `w h ≥ a_min` n'est pas une inégalité linéaire. L'ensemble
`{(w,h) > 0 : w h ≥ a_min}` est toutefois **convexe** : c'est un super-niveau de
`log w + log h`, concave (Boyd & Vandenberghe, §3.1.5–3.1.6). On le remplace par
ses tangentes (Kelley, *SIAM J.* 8, 1960) :

```
h₀ w + w₀ h ≥ 2 a_min
```

au point de l'hyperbole `w₀ h₀ = a_min`. C'est aussi l'AM-GM (Hardy, Littlewood,
Pólya, *Inequalities*, 2e éd., Cambridge, 1952, théorème 16).

## Distance au plan proposé

Minimiser `Σ |x_i − x̂_i|` n'est pas linéaire. L'épigraphe (Bertsimas & Tsitsiklis,
*Introduction to Linear Optimization*, Athena Scientific, 1997, §1.3) introduit
`e_i ≥ |x_i − x̂_i|` et minimise `Σ e_i`. Les `x̂_i` entrent dans les **contraintes**,
jamais dans le vecteur de coûts `c = (0, …, 0, 1, …, 1)`.

## Vérification

Le solveur n'est pas cru. `certify.preuve` recompte aires d'intersection (Shapely /
GEOS), écart d'aire union–contour, surfaces et murs porteurs. `valide` est la
conjonction de quatre booléens, aucun n'est probabiliste.

**Voir aussi :** [Corriger un plan](../galerie/01-corriger-un-plan.md),
[Les deux garanties](deux-garanties.md),
[formulaire — polytope](../formules/polytope-separe.md),
[formulaire — L1](../formules/epigraphe-l1.md),
[formulaire — coupes](../formules/coupes-surface.md).
