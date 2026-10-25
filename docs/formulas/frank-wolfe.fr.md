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
- `status`, la raison de l'arrêt (tableau ci-dessous). Seul `converged` affirme une
  stationnarité ; **aucun statut ne signifie « optimum global »**.

| `status` | Sens | Point renvoyé |
|---|---|---|
| `converged` | \(g \le\) `tol` | dans \(P\), stationnaire à `tol` près |
| `max_iter` | budget d'itérations épuisé | dans \(P\), écart en ce point rapporté |
| `line_search_failed` | 12 divisions du pas par deux n'ont jamais amélioré l'objectif | dans \(P\), non stationnaire |
| `lp_not_optimal` | l'oracle n'a pas rendu d'optimum | dans \(P\), écart \(+\infty\) après un déplacement |
| `oracle_inconsistent` | l'oracle dit « optimal » mais son sommet sort de \(P\) ou est pire que \(x_k\) | dans \(P\) (le sommet n'est **pas** utilisé), écart \(+\infty\) |
| `stalled` | `stall_window` pas consécutifs ont chacun gagné \(<\) `stall_tol` (sur demande) | dans \(P\), non stationnaire |

Tout statut renvoie un point de \(P\) : la validité **géométrique** ne dépend jamais du
statut, l'affirmation d'optimisation en dépend toujours. Un appelant qui annonce un plan
« optimisé » doit vérifier `FrankWolfeResult.converged` (ou `Trace.converged`), et pas
seulement qu'un plan est revenu.

## Hypothèses, et comment chacune est imposée

- \(x_0\in P\) (en pratique : la sortie L1 du jalon 2). **Vérifié** : un départ qui viole
  \(P\) (boîte de budget comprise) de plus de `tolerances.FW_FEASIBILITY_M`
  (\(10^{-6}\) m) lève `InvariantViolation` en nommant la ligne la plus violée, avant
  tout PL.
- L'oracle a raison. **Vérifié à chaque itération** : un sommet \(s_k\) hors de \(P\)
  (au-delà de `FW_FEASIBILITY_M`), ou d'écart inférieur à \(-\)`FW_FEASIBILITY_M`
  \(\lVert\nabla f\rVert_1\) (pire que \(x_k\) lui-même, ce qu'aucun minimiseur ne peut
  être), n'est jamais visé : l'exécution s'arrête sur `oracle_inconsistent` en \(x_k\).
- Chaque itéré reste dans \(P\). **Vérifié** : un pas qui sort de \(P\) (possible
  seulement avec une `StepStrategy` injectée fautive) lève `InvariantViolation`.
- \(P\) est le domaine que vérifie le validateur final, ou un sous-ensemble. Dans
  `legalize`, \(P\) est le polytope L1 aux contacts figés, la boîte de budget et les
  cordes intérieures de surface : tout point en respecte les contraintes d'origine
  (aucun recouvrement, contour, côtés porteurs, \(w h \ge a\)), et le plan décodé est
  revérifié par `certify.proof.verify_exactly` sur les contraintes non linéaires
  **d'origine**, jamais sur leur approximation linéaire. Les coupes tangentes des
  [coupes de surface](area-cuts.md) (approximation extérieure) ne sont **pas**
  utilisées par Frank-Wolfe.
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

## Déplacement : pénalité, mesures, et pourquoi le budget sature

**Pénalité.** `frank_wolfe(..., penalty=λ, reference=x̂)` maximise

\[
F(x) = f(x) - \tfrac{\lambda}{2}\lVert x - \hat x\rVert_2^2 ,
\]

dont le gradient \(\nabla f(x) - \lambda (x - \hat x)\) est ce que reçoit l'oracle. La
recherche linéaire et la monotonie portent sur \(F\) ; `value` rapporte toujours \(f\)
et `objective` rapporte \(F\), si bien qu'une calibration de \(f\) reste valable.
\(\lambda\) s'exprime en unités de l'indicateur par m² ; \(\lambda = 0\) (défaut) est le
substitut seul.

**Boîte de budget et son diagnostic.** `frank_wolfe(..., budget=Δ, reference=x̂)`
intersecte \(P\) avec \(\lVert x-\hat x\rVert_\infty \le Δ\) (en gardant toujours
\(x_0\)). La trace enregistre alors `Trace.budget_active`, les colonnes sur la boîte au
point renvoyé, et `Trace.active_bounds`, toutes les bornes et lignes serrées.
`Trace.displacements` donne \(\lVert x_k-\hat x\rVert_\infty\) pour chaque itéré.

**Mesures.** `solve.displacement.measure_displacement(proposed, corrected)` mesure,
pièce par pièce, le plus grand déplacement de côté (m), la variation de surface signée
et relative, et le déplacement du centre de chaque ouverture dérivé de son mur ;
`combined(wall=, area=, opening=)` les pondère explicitement (il n'existe pas de poids
canoniques). `summarize(values)` renvoie moyenne, médiane, intervalle 10–90 %, extrêmes
et histogramme ; `count_saturated(values, budget=Δ)` compte les variantes qui ont
atteint Δ. Respecter un budget **n'est pas** préserver le projet : ces nombres ne
décrivent que la géométrie.

**Pourquoi le budget sature (jalon 9 : 36 variantes sur 48 à exactement 3,00 m).**
C'est le comportement attendu de la méthode, pas un artefact numérique :

1. Sans pénalité, rien dans \(f\) ne récompense la proximité à \(\hat x\). Partout où
   \(f\) croît à travers la boîte, son maximiseur sur \(P \cap\) boîte est un sommet, et
   l'oracle renvoie exactement de tels sommets. Sur la grille synthétique 5 × 3
   (15 pièces, `AnalyticSurrogate`, azimuts 0/90/180/270°), toute exécution avec
   Δ ≤ 0,5 m converge en 2 à 3 itérations **sur la boîte** (déplacement = Δ).
2. Pour un Δ plus grand, l'exécution s'arrête avant la boîte, mais sur
   `line_search_failed`, pas sur une convergence : le substitut analytique n'est lisse
   que par morceaux, son gradient concorde avec les différences finies à
   \(h = 10^{-7}\) m mais pas à \(10^{-5}\) m, alors que le plus petit pas essayé vaut
   \(2/(k+2)/2^{12}\) d'une direction de plusieurs mètres. Le gain n'est alors pas
   monotone en Δ (azimut 0° : +8,70 à Δ = 2 m, +8,31 à Δ = 3 m).
3. Une pénalité ramène l'optimum dans la boîte : sur le même plan à l'azimut 0°,
   Δ = 1 m, λ = 1 donne un déplacement de 0,28 m pour un gain de 1,18 (contre 1,00 m et
   4,99 sans pénalité) ; λ = 4 donne 0,07 m pour 0,28.

Un budget saturé signifie donc « le substitut aurait déplacé plus loin », et le gain
rapporté est une fonction de Δ. Le rapporter comme tel : le gain **avec** son
déplacement, pour plusieurs Δ et λ (`solve.sweep.sweep`), jamais un gain unique à un
budget unique.

## Budgets d'itérations

`solve.sweep.sweep(poly, surrogate, orientation, start, max_iters=..., budgets=...,
penalties=...)` relance le même départ sur la grille et renvoie, par exécution,
`status`, `iterations`, le `gain` du substitut, `gap`, `displacement`, `budget_bound`
et le temps horloge `time_ms` (seule colonne non reproductible). `success_rate(rows)`
renvoie `(converged, total)`, une paire à passer à un intervalle de Wilson, jamais un
ratio nu. Sur la grille synthétique ci-dessus, 3 exécutions sur 18 par azimut
convergent, toutes contraintes par le budget avec λ = 0 ; passer `max_iter` de 50 à
200 ne change rien, car les exécutions s'arrêtent d'abord sur la recherche linéaire.
Le défaut `max_iter = 50` n'y est donc pas le facteur limitant ; la régularité du
substitut l'est.

## Reproductibilité

`Trace.parameters` enregistre chaque réglage en paires `(nom, texte)` triées :
`max_iter`, `tol`, `budget`, `reference`, `penalty`, `away_steps`, `strategy` (son
`repr`), `stall_window`, `stall_tol`, la règle de pas et `FW_FEASIBILITY_M`. Avec les
itérés \(x_k\), valeurs, écarts, pas et marqueurs de pas d'éloignement déjà présents dans
`Trace.iterations`, une exécution peut être rejouée et auditée sans la relancer. Le
solveur est déterministe : deux exécutions aux mêmes entrées donnent des traces
identiques (seul `lp_ms` diffère).

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

`frank_wolfe` → `FrankWolfeResult` (`x`, `value`, `objective`, `gap`, `status`,
`converged`, `iterations`, `trace`, `duals`). `Trace.parameters`,
`Trace.active_bounds`, `Trace.budget_active`, `Trace.displacements` et
`Trace.objectives` servent le diagnostic ci-dessus. `Trace.iterates`, `Trace.values`, `Trace.status` et
`Trace.final_gap` servent les critères d'acceptation (les noms français `iteres`,
`objectif`, `ecarts` et les champs `valeur`, `pas` de `Iteration` restent comme alias
dépréciés).

## Usage

| Faire | Ne pas faire |
|---|---|
| Brancher n'importe quel `Surrogate` | Importer `light.analytic` depuis `solve` |
| Rapporter un gain avec son déplacement, `budget_active` et `status` | Rapporter un gain à un seul budget comme « le » gain, ou une exécution `line_search_failed` comme optimisée |
| Lire `gap` avec `status` comme diagnostic de stationnarité | Lire `gap` comme une borne sur l'optimum (aucun substitut livré n'est concave), ou le confondre avec une couverture \(1-\alpha\) |

## Source

Frank & Wolfe (1956), *An algorithm for quadratic programming*, Naval Research
Logistics Quarterly. Lacoste-Julien & Jaggi (2015), *On the Global Linear Convergence
of Frank-Wolfe Optimization Variants*, NeurIPS. Lacoste-Julien (2016), *Convergence
Rate of Frank-Wolfe for Non-Convex Objectives*, arXiv:1607.00345.
[Bibliographie](sources.md).
