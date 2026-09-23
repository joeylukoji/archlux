# Ordre relatif et graphe de contraintes

**Code :** `geom.graphe.deduire_ordre`, `construire_graphe`, `reduction_transitive`.

## Énoncé

Pour deux rectangles \(A,B\), le *jeu* sur l'axe \(x\) est

\[
\delta_x(A,B)=\max\bigl(x_B-(x_A+w_A),\; x_A-(x_B+w_B)\bigr).
\]

\(\delta_x>0\) : les projections sur \(x\) sont disjointes ; \(\delta_x=0\) : elles
se touchent ; \(\delta_x<0\) : elles se recouvrent. Idem \(\delta_y\) en hauteur.

**Règle fondatrice.** Toute paire reçoit **exactement une** arête, sur l'axe où les
pièces sont réellement disjointes (le plus grand jeu si les deux le sont). À défaut
des deux jeux négatifs (chevauchement), l'axe du plus grand écart entre *centres*
tranche. Le *sens* de l'arête suit l'ordre total \((\text{centre}, \mathrm{id})\).

Une arête horizontale \(A\to B\) se lit « \(A\) est à gauche de \(B\) » et deviendra

\[
x_A+w_A\le x_B.
\]

## Hypothèses

- Pièces rectangulaires, côtés parallèles aux axes.
- Identifiants comparables (ordre lexicographique) pour casser les égalités de centres.
- Tolérance de contact \(\tau=10^{-9}\,\mathrm{m}\) : \(\delta\ge -\tau\) compte comme
  disjoint. Sans elle, \(1+3{,}47=4{,}470000000000001\) en IEEE-754 fait passer deux
  pièces jointives pour recouvrantes.

## Dérivation — acyclicity

Sur un axe fixé, l'arête va toujours du plus petit centre vers le plus grand (à
\(\mathrm{id}\) près). L'ensemble des arêtes d'un axe est donc un sous-graphe d'un
**ordre total**, donc un DAG. Un cycle « \(A\) à gauche de \(B\) à gauche de \(A\) »
est impossible *par construction* de `deduire_ordre`. `construire_graphe` le revérifie
(`networkx.is_directed_acyclic_graph`) au cas où l'ordre viendrait d'ailleurs.

## Dérivation — réduction transitive

Si \(A\to B\) et \(B\to C\), alors \(x_A+w_A\le x_B\) et \(x_B+w_B\le x_C\). Comme
\(w_B\ge 0\), \(x_A+w_A\le x_C\) : l'arête \(A\to C\) est *impliquée*. La réduction
transitive (Aho, Garey & Ullman, 1972) retire ces arêtes sans changer la fermeture
d'ordre. 15 pièces : \(\sim 210\) contraintes brutes, \(\sim 30\) après réduction.

`networkx.transitive_reduction` omet les nœuds isolés ; ils sont **réinjectés** :
une pièce séparée seulement sur l'autre axe disparaîtrait, et le polytope perdrait
ses bornes.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Lire l'ordre d'un plan *proposé* (le générateur décide) | Choisir l'axe du plus grand écart de centres alors que les pièces se recouvrent sur cet axe — la contrainte produite est déjà violée par un plan correct |
| Réduire avant d'assembler \(A x\le b\) | Tester `a_separation` *après* réduction : une paire séparée par transitivité n'a plus d'arête directe |
| Tolérer le contact à \(10^{-9}\,\mathrm{m}\) | Traiter un `set` d'arêtes : l'ordre d'itération changerait les lignes de \(A\) |

## Source

- Otten (1982), DAC — pavages en guillotine, ordre de coupes.
- Lengauer (1990), ch. 10 — graphe de contraintes \(x_a+w_a\le x_b\).
- Aho, Garey & Ullman (1972), *SIAM J. Comput.* — réduction transitive,
  [doi:10.1137/0201008](https://doi.org/10.1137/0201008).

Détail des éditions : [bibliographie](sources.md).
