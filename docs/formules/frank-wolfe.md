# Frank-Wolfe sur le polytope

**Code :** `solve.frank_wolfe`.

## Énoncé

On maximise un substitut \(f\) (concave ou non) sur le
[polytope](polytope-separe.md) \(P\) :

\[
\max_{x\in P} f(x).
\]

À l'itéré \(x_k\), l'oracle linéaire est **le même LP** que la légalisation :

\[
s_k\in\arg\max_{s\in P}\langle\nabla f(x_k),s\rangle
=\arg\min_{s\in P}\langle -\nabla f(x_k),s\rangle,
\]

soit `lmo.resoudre(poly, c=-gradient, depart=x_k)`. Le pas standard est
\(\gamma_k=\min\{2/(k+2),\gamma_{\max}\}\), avec recul si \(f\) diminue. Le gap

\[
g_k=\langle\nabla f(x_k),s_k-x_k\rangle
\]

majore \(f^\star-f(x_k)\) **lorsque \(f\) est concave**.

## Hypothèses

- \(x_0\in P\) (en pratique : sortie L1 du jalon 2).
- Chaque appel passe `depart=x` : le modèle GLOP est réutilisé
  (`ARCHITECTURE.md` §10).
- Les itérés sont des combinaisons convexes de sommets, donc dans \(P\).
- Un budget \(\Delta\) se traduit par la boîte \(\lVert x-x_0\rVert_\infty\le\Delta\).
- Après L1, `figer_contacts` transforme les séparations saturées en égalités
  et colle \(x,y\) aux bords saturés du contour : Frank-Wolfe reste un pavage
  (pas de jour) tout en bougeant les cloisons internes. Les largeurs minimales
  saturées restent libres : une pièce étroite peut s'agrandir.

## Dérivation

Frank–Wolfe (1956) : direction vers un sommet, pas décroissant. Les pas
d'écartement (away-steps) de Lacoste-Julien & Jaggi (2015) retirent de la masse
au plus mauvais sommet actif, ce qui accélère sur les faces.

L'identité oracle = légaliseur est le cœur du projet : un seul solveur, deux
vecteurs \(c\).

## Code

`frank_wolfe` → `ResultatFW` (`x`, `valeur`, `gap`, `trace`).
`Trace.iteres` / `Trace.objectif` pour les critères d'acceptation.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Brancher n'importe quel `Substitut` | Importer `light.analytique` depuis `solve` |
| Lire `gap` comme borne d'optimisation | Le confondre avec une couverture \(1-\alpha\) |

## Source

Frank & Wolfe (1956), *An algorithm for quadratic programming*, Naval Research
Logistics Quarterly. Lacoste-Julien & Jaggi (2015), *On the Global Linear
Convergence of Frank-Wolfe Optimization Variants*, NeurIPS.
[Bibliographie](sources.md).
