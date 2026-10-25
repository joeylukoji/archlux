# Ordre relatif et graphe de contraintes

**Code :** `geom.graph.deduce_order`, `build_graph`, `transitive_reduction`.

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
  disjoint. Sans elle, \(1+3.47=4.470000000000001\) en IEEE-754 fait passer deux
  pièces jointives pour recouvrantes.

## Dérivation — acyclicity

Sur un axe fixé, l'arête va toujours du plus petit centre vers le plus grand (à
\(\mathrm{id}\) près). L'ensemble des arêtes d'un axe est donc un sous-graphe d'un
**ordre total**, donc un DAG. Un cycle « \(A\) à gauche de \(B\) à gauche de \(A\) »
est impossible *par construction* de `deduce_order`. `build_graph` le revérifie
(`networkx.is_directed_acyclic_graph`) au cas où l'ordre viendrait d'ailleurs.

## Dérivation — réduction transitive

Si \(A\to B\) et \(B\to C\), alors \(x_A+w_A\le x_B\) et \(x_B+w_B\le x_C\). Comme
\(w_B\ge 0\), \(x_A+w_A\le x_C\) : l'arête \(A\to C\) est *impliquée*. La réduction
transitive (Aho, Garey & Ullman, 1972) retire ces arêtes sans changer la fermeture
d'ordre. 15 pièces : \(\sim 210\) contraintes brutes, \(\sim 30\) après réduction.

`networkx.transitive_reduction` omet les nœuds isolés ; ils sont **réinjectés** :
une pièce séparée seulement sur l'autre axe disparaîtrait, et le polytope perdrait
ses bornes.

## Portée : une seule topologie, fixée

**Comment la séquence de contraintes est produite.** Une fois, à partir du plan
**proposé**, par `deduce_order` (et `WallSide` pour les murs porteurs, les coutures des
pièces fusionnées pour `merges=`, la grille de `deduce_grid` avec `tiling=True`). Elle
n'est jamais régénérée pendant la résolution : la passe L1 classique et Frank-Wolfe
travaillent tous deux dans le polytope de cet unique ordre, et Frank-Wolfe fige en plus
les contacts saturés par la passe L1 (`freeze_contacts`).

**Ce qu'elle peut représenter.** Tout plan qui conserve, pour chaque paire de pièces,
le côté de l'arête choisie ci-dessus (« \(A\) à gauche de \(B\) », « \(A\) sous \(B\) »),
chaque pièce du bon côté de chaque mur porteur et (avec `merges=`) l'ordre de découpe de
chaque pièce fusionnée. Dans cet ensemble, le solveur ne change **que les dimensions et
les positions**.

**Ce qu'elle ne peut pas représenter.** Tout ce qui change la topologie : échanger deux
pièces, faire passer une pièce de la gauche d'une autre au-dessus d'elle, créer ou
supprimer une adjacence que l'ordre interdit, ajouter, supprimer, fusionner ou scinder
une pièce, transformer un L en Z, ou faire traverser un mur porteur à une pièce. La
méthode est une légalisation de la topologie du générateur, pas une recherche
d'agencement : un plan dont le défaut ne peut disparaître que par un changement
topologique est hors de sa portée, par construction.

**Comment l'infaisabilité est détectée, et ce qu'elle signifie.** Un refus est toujours
typé, jamais un « au mieux » silencieux :

| Exception | Détectée par | Signifie |
|---|---|---|
| `InconsistentOrder` | un cycle dans le graphe de contraintes (`build_graph`) | l'ordre lui-même est contradictoire |
| `MissingSeparation` | une paire sans arête | l'ordre ne sépare pas deux pièces |
| `Infeasible` avec certificat de Farkas | le PL L1 (`lmo.solver.solve`), certificat vérifié exactement | **pour cet ordre**, le programme ne tient pas dans l'enveloppe ; un autre ordre le pourrait |
| `Infeasible` venant de `restrict_to_budget` | la boîte de budget manque les bornes d'une variable | le budget de déplacement est trop petit pour ce plan |
| `GapNeedsTiling` | la preuve exacte ne trouve qu'un jour | relancer avec `tiling=True` |
| `GridNotRecoverable` | `deduce_grid` | les pièces ne tombent pas dans les cellules d'une grille |

Un certificat de Farkas prouve l'infaisabilité **du polytope de l'ordre proposé**, pas
du programme de pièces : il ne dit pas qu'aucun plan valide n'existe, seulement qu'aucun
n'existe avec cette topologie.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Lire l'ordre d'un plan *proposé* (le générateur décide) | Choisir l'axe du plus grand écart de centres alors que les pièces se recouvrent sur cet axe — la contrainte produite est déjà violée par un plan correct |
| Réduire avant d'assembler \(A x\le b\) | Tester `has_separation` *après* réduction : une paire séparée par transitivité n'a plus d'arête directe |
| Tolérer le contact à \(10^{-9}\,\mathrm{m}\) | Traiter un `set` d'arêtes : l'ordre d'itération changerait les lignes de \(A\) |

## Source

- Otten (1982), DAC — pavages en guillotine, ordre de coupes.
- Lengauer (1990), ch. 10 — graphe de contraintes \(x_a+w_a\le x_b\).
- Aho, Garey & Ullman (1972), *SIAM J. Comput.* — réduction transitive,
  [doi:10.1137/0201008](https://doi.org/10.1137/0201008).

Détail des éditions : [bibliographie](sources.md).
