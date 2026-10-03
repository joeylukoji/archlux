# Frank-Wolfe sur le polytope

**Code :** `solve.frank_wolfe`.

## Énoncé

On maximise un substitut \(f\) (concave ou non) sur le
[polytope](separated-polytope.md) \(P\) :

\[
\max_{x\in P} f(x).
\]

À l'itéré \(x_k\), l'oracle linéaire est **le même PL** que la légalisation :

\[
s_k\in\arg\max_{s\in P}\langle\nabla f(x_k),s\rangle
=\arg\min_{s\in P}\langle -\nabla f(x_k),s\rangle,
\]

c'est-à-dire `lmo.solver.solve(poly, c=-gradient, start=x_k)`. Le pas standard est
\(\gamma_k=\min\{2/(k+2),\gamma_{\max}\}\), divisé par deux tant que \(f\) décroît. L'écart

\[
g_k=\langle\nabla f(x_k),s_k-x_k\rangle
\]

borne \(f^\star-f(x_k)\) **lorsque \(f\) est concave**.

**Ce que l'écart signifie ici.** Aucun des substituts livrés n'est concave : le substitut
analytique est le produit d'un terme bilinéaire et d'une exponentielle convexe (AUDIT.md
§5.1). Pour un \(f\) non concave, l'écart n'est qu'une mesure de **stationnarité** au
premier ordre (il s'annule aux points stationnaires, Lacoste-Julien 2016), jamais une
borne sur \(f^\star - f(x)\). Le code rapporte donc :

- `gap`, calculé **au point renvoyé** (un PL de plus quand l'exécution s'arrête sur
  `max_iter`), et \(+\infty\) dès qu'il est inconnu (aucun PL n'a réussi, ou le PL au
  point renvoyé a échoué), pour qu'un échec ne se lise jamais comme « optimum atteint » ;
  `Trace.final_gap` porte la même valeur ;
- `status`, la raison de l'arrêt : `converged` (\(g \le\) `tol`), `line_search_failed`
  (aucun pas le long de la direction n'a amélioré \(f\)), `lp_not_optimal` ou `max_iter`.

## Hypothèses

- \(x_0\in P\) (en pratique : la sortie L1 du jalon 2).
- Chaque appel passe `start=x` : le modèle GLOP est réutilisé (`ARCHITECTURE.md` §10).
- Les itérés sont des combinaisons convexes de sommets, donc dans \(P\).
- Un budget \(\Delta\) est la boîte \(\lVert x-\hat x\rVert_\infty\le\Delta\) autour du
  plan **proposé** \(\hat x\), partagée par la passe classique et Frank-Wolfe, afin
  qu'il ne soit dépensé qu'une fois. La centrer sur le point L1 \(x_0\) autorisait
  jusqu'à \(2\Delta\) au total (mesuré : 0,55 m pour \(\Delta = 0.3\) m). La boîte
  contient toujours \(x_0\), qui ne respecte le budget qu'à la tolérance du PL près
  lorsque le budget est saturé. La preuve vérifie \(\max \lvert x - \hat x\rvert \le
  \Delta\) ; un budget trop petit pour le plan lève `Infeasible`.
- Après L1, `freeze_contacts` transforme les séparations saturées en égalités et fixe
  \(x, y\) aux bords saturés du contour : Frank-Wolfe conserve un pavage (aucun jour
  entre pièces) tout en déplaçant les cloisons intérieures. Les largeurs minimales
  saturées restent libres : une pièce étroite peut grandir.

## Dérivation

Frank-Wolfe (1956) : se déplacer vers un sommet, avec un pas décroissant. Les pas
d'éloignement (*away steps*) de Lacoste-Julien & Jaggi (2015) retirent de la masse au
pire sommet actif, ce qui accélère la convergence sur les faces.

L'itéré est conservé sous la forme \(x=\sum_i w_i v_i\) sur des sommets actifs \(v_i\)
(poids \(w_i>0\), \(\sum_i w_i=1\)). Avec \(a=\arg\min_i\langle\nabla f(x),v_i\rangle\),
la direction d'éloignement \(d_A=x-v_a\) est prise lorsque \(\langle\nabla
f,d_A\rangle>\langle\nabla f,s-x\rangle\) et \(w_a<1\) ; son pas maximal est
\(\gamma_{\max}=w_a/(1-w_a)\), sinon \(\gamma_{\max}=1\). La mise à jour des poids est

- pas simple : \(w\leftarrow(1-\gamma)w\), puis \(w_s\mathrel{+}=\gamma\) (\(s\) ajouté
  s'il est nouveau) ;
- pas d'éloignement : \(w\leftarrow(1+\gamma)w\), puis \(w_a\mathrel{-}=\gamma\) (à
  \(\gamma_{\max}\), \(w_a=0\)) ;

les sommets dont le poids tombe à \(\le 10^{-12}\) sont retirés et les autres
renormalisés. La recherche linéaire essaie au plus 12 divisions par deux et rapporte
`line_search_failed` sinon.

L'identité oracle = légaliseur est le cœur du projet : un seul solveur, deux vecteurs de
coût \(c\).

## Code

`frank_wolfe` → `FrankWolfeResult` (`x`, `value`, `gap`, `status`, `iterations`,
`trace`, `duals`). `Trace.iterates`, `Trace.values`, `Trace.status` et
`Trace.final_gap` servent les critères d'acceptation (les noms français `iteres`,
`objectif`, `ecarts` et les champs `valeur`, `pas` de `Iteration` restent comme alias
dépréciés).

## Usage

| Faire | Ne pas faire |
|---|---|
| Brancher n'importe quel `Surrogate` | Importer `light.analytic` depuis `solve` |
| Lire `gap` avec `status` comme diagnostic de stationnarité | Lire `gap` comme une borne sur l'optimum (aucun substitut livré n'est concave), ou le confondre avec une couverture \(1-\alpha\) |

## Source

Frank & Wolfe (1956), *An algorithm for quadratic programming*, Naval Research
Logistics Quarterly. Lacoste-Julien & Jaggi (2015), *On the Global Linear Convergence
of Frank-Wolfe Optimization Variants*, NeurIPS. Lacoste-Julien (2016), *Convergence
Rate of Frank-Wolfe for Non-Convex Objectives*, arXiv:1607.00345.
[Bibliographie](sources.md).
