# Pipeline de la légalisation classique

**Code :** `api.legalize` (`objective is None`).

## Énoncé

\[
\min_{x,e}\; \sum_i e_i
\quad\text{s.c.}\quad
x\in P,\;
e\ge \lvert x-\hat x\rvert,\;
(w_p,h_p)\in K_p,
\]

où \(P\) est le [polytope d'ordre](separated-polytope.md), \(K_p\) le
[super-niveau de surface](area-cuts.md) de la pièce \(p\), et \(\hat x\) le
plan proposé [vectorisé](l1-epigraph.md).

Puis : dévectoriser, [vérifier exactement](exact-proof.md), attacher le
`Certificate`. Si la preuve est fausse → `InvariantViolation` (bogue interne, jamais
silencieux). Si le LP est infaisable → `Infeasible` avec
[Farkas](farkas.md).

## Chaîne, une ligne par étape

1. `deduce_order` — le générateur décide l'ordre ([graphe](relative-order.md)).
2. `build_polytope` — \(Ax\le b\).
3. `extend_l1_slack` — \((x,e)\in\mathbb{R}^{2n}\).
4. `gradient_distance` — \(c=(0_n,1_n)\).
5. `solve_with_areas` — GLOP + Kelley + bornes.
6. `devectorize` — murs et baies suivent (baie relative au mur).
7. `verify_exactly(..., reference=plan)` — \(\delta_\infty\).
8. `Certificate(geometry=..., performance=None, duals=...)`.

`performance is None` : en mode classique il n'y a **rien de probabiliste** à
affirmer.

## Branche performantielle (`objective=Surrogate`)

Après l'étape 8, le point L1 devient \(x_0\). Les contacts saturés passent
en égalités (`freeze_contacts`) : Frank-Wolfe reste un pavage. Puis les surfaces
minimales sont remplacées par une approximation polyédrale **intérieure**
(`inner_area_constraints`, voir [coupes de surface](area-cuts.md)) : tout point du
domaine, donc tout itéré, respecte chaque surface minimale, et aucune coupe tangente
n'est nécessaire.
Puis [Frank-Wolfe](frank-wolfe.md) maximise le substitut, **même oracle LP**,
`start=x` à chaque tour. La sortie est revérifiée exactement ; un itéré
invalide lève `InvariantViolation` — pas de repli silencieux vers L1.
Avec `legalize(..., calibration=...)`, la prédiction du substitut au plan renvoyé est
bornée par `certify.bound.bound_selected_plan`, dans le régime **sélectionné** :
l'optimiseur a choisi le plan, donc la couverture nominale n'est pas garantie et le
rapport le dit. La calibration est vérifiée avant toute résolution. Sans calibration,
`performance is None` et le rapport écrit `NOT EVALUABLE`.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| `legalize(plan, ctx)` sur un pavage presque valide | Attendre 100 % de succès sur `plans_quelconques` × enveloppe petite : le programme peut ne pas tenir → `Infeasible` |
| Lire `q.certificate.geometry.valid` | Agréger preuve et prédiction en un score |
| Importer `light.protocol.Surrogate` seulement | Importer `bench` depuis `api` (interdit par `tests/test_dependencies.py`) |

Budget `ARCHITECTURE.md` §9 : \(< 20\,\mathrm{ms}\) pour 15 pièces.

## Source

Composition des fiches de ce dossier ; pas un théorème séparé.
