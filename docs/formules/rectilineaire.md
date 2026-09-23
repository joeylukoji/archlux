# Décomposition rectilinéaire

**Code :** `geom.rectilineaire.decomposer` / `recomposer` / `etendre_fusions`.

## Énoncé

Un polygone simple **rectilinéaire** (arêtes uniquement horizontales ou verticales)
admet une partition en rectangles. Convention **fixée** (`MILESTONE-6.md`) :

1. parmi les sommets réflexes, considérer les **coupes verticales** intérieures ;
2. choisir celle d'abscisse minimale (gauche d'abord) ; en cas d'égalité, ordonnée minimale ;
3. récurrence jusqu'à n'obtenir que des rectangles (au plus 4).

Les rectangles solidaires d'une même pièce métier sont reliés par des **fusions** :

\[
x_i + w_i = x_j
\quad\text{(partage\_bord\_droit)},\qquad
y_i + h_i = y_j
\quad\text{(partage\_bord\_haut)}.
\]

Ces égalités entrent dans \(A_{\mathrm{eq}}\) via `etendre_fusions` ; le polytope
reste linéaire.

## Hypothèses

- Polygone simple, valide, sans trou.
- Arêtes axis-alignées.
- La décomposition d'un L n'est pas unique en général : **sans la convention
  ci-dessus, les résultats ne sont pas reproductibles.**

## Code

| Symbole | Fonction |
|---|---|
| partition | `decomposer` |
| union | `recomposer` |
| \(A_{\mathrm{eq}}\) | `etendre_fusions` → `legalize(..., fusions=)` |

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Découper puis passer les sous-rectangles comme `Piece` | Stocker un polygone L brut dans `Plan.pieces` |
| Fixer la convention verticale-gauche | Changer l'ordre de coupe selon l'entrée |
| Budget < 40 ms pour 15 pièces dont 4 en L | Décomposition trop fine (grille cellulaire) |

## Source

Convention de projet (`MILESTONE-6.md` §2) ; partition guillotine classique.
