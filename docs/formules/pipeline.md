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

où \(P\) est le [polytope d'ordre](polytope-separe.md), \(K_p\) le
[super-niveau de surface](coupes-surface.md) de la pièce \(p\), et \(\hat x\) le
plan proposé [vectorisé](epigraphe-l1.md).

Puis : dévectoriser, [vérifier exactement](preuve-exacte.md), attacher le
`Certificat`. Si la preuve est fausse → `InvariantViole` (bogue interne, jamais
silencieux). Si le LP est infaisable → `Infaisable` avec
[Farkas](farkas.md).

## Chaîne, une ligne par étape

1. `deduire_ordre` — le générateur décide l'ordre ([graphe](ordre-relatif.md)).
2. `construire_polytope` — \(Ax\le b\).
3. `etendre_ecarts_l1` — \((x,e)\in\mathbb{R}^{2n}\).
4. `gradient_distance` — \(c=(0_n,1_n)\).
5. `resoudre_avec_surfaces` — GLOP + Kelley + bornes.
6. `devectoriser` — murs et baies suivent (baie relative au mur).
7. `verifier_exactement(..., reference=plan)` — \(\delta_\infty\).
8. `Certificat(geometrie=..., performance=None, duaux=...)`.

`performance is None` : en mode classique il n'y a **rien de probabiliste** à
affirmer.

## Branche performantielle (`objective=Substitut`)

Après l'étape 8, le point L1 devient \(x_0\). Les contacts saturés passent
en égalités (`figer_contacts`) : Frank-Wolfe reste un pavage. Puis
[Frank-Wolfe](frank-wolfe.md) maximise le substitut, **même oracle LP**,
`depart=x` à chaque tour. La sortie est revérifiée exactement ; un itéré
invalide lève `InvariantViole` — pas de repli silencieux vers L1.
Le score du substitut est borné **hors** de `legalize` : calibrer, puis
`certify.borne.construire_borne` (la couche `api` n'importe pas `uq`).
Sans calibration, `performance is None` et le rapport écrit `NON EVALUABLE`.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| `legalize(plan, ctx)` sur un pavage presque valide | Attendre 100 % de succès sur `plans_quelconques` × enveloppe petite : le programme peut ne pas tenir → `Infaisable` |
| Lire `q.certificat.geometrie.valide` | Agréger preuve et prédiction en un score |
| Importer `light.protocole.Substitut` seulement | Importer `bench` depuis `api` (interdit par `tests/test_dependances.py`) |

Budget `ARCHITECTURE.md` §9 : \(< 20\,\mathrm{ms}\) pour 15 pièces.

## Source

Composition des fiches de ce dossier ; pas un théorème séparé.
