# Simplexe, duaux et Farkas

**Code :** `lmo.solveur.resoudre`, `_certificat_farkas`, `_est_faisable`.

## Énoncé — primal

\[
\min_x \; c^\top x
\quad\text{s.c.}\quad
Ax \le b,\quad
A_{\mathrm{eq}} x = b_{\mathrm{eq}},\quad
\ell \le x \le u,
\]

plus les [coupes](coupes-surface.md) \(\sum_j \alpha_j x_j \ge \beta\).

**Ce module ne sait pas d'où vient \(c\).** Distance L1 ou \(-\nabla\) d'éclairement :
même oracle (`ARCHITECTURE.md` §2).

Backend : OR-Tools **GLOP** (simplexe).

## Duaux

Si `duaux=True`, les prix sont extraits **dans l'ordre des lignes de \(A\)** — le
seul ordre appariable avec `Polytope.origines`. Les coupes et les égalités ne sont
pas dans ce vecteur au jalon 2 : un dual de coupe de surface n'est pas encore
libellé. Les composantes \(\lvert y_i\rvert \le 10^{-9}\) sont omises à l'API.

Un prix dual se lit : « relâcher cette contrainte d'un mètre change l'objectif de
\(y_i\) ». C'est la dualité LP standard (Bertsimas & Tsitsiklis, ch. 4).

## Infaisable vs non borné

GLOP rend le code `INFEASIBLE` aussi pour un problème **non borné**. Discriminant :
le LP à objectif nul sur le même système. Un LP à objectif nul ne peut pas être
non borné ; s'il trouve un point, l'échec venait de \(c\), pas du programme.

## Dérivation — certificat de Farkas (phase I)

Lemme de Farkas (Schrijver, 1986, §7.3 ; Bertsimas & Tsitsiklis, ch. 4) : le
système \(Ax\le b\) est infaisable si et seulement s'il existe \(y\ge 0\) tel que

\[
A^\top y = 0 \quad\text{et}\quad b^\top y < 0
\]

(forme d'alternative pour les inégalités ; les égalités et les bornes se ramènent
à ce cas). Un tel \(y\) *désigne* les contraintes en conflit.

**Ce que le code calcule.** Problème auxiliaire (phase I) : relâcher chaque
inégalité \(a_i x \le b_i\) par \(s_i\ge 0\),

\[
\min\; \sum_i s_i
\quad\text{s.c.}\quad
a_i x - s_i \le b_i.
\]

Toujours faisable. Si l'optimum est strictement positif, le primal ne l'est pas.
Les duaux des contraintes relâchées, **négués** (OR-Tools rend le signe opposé à
la convention \(y\ge 0\) pour une ligne \(\le\)), sont le certificat renvoyé.
Les coupes \(\ge\) sont relâchées dans l'autre sens ; sans cela une coupe
impossible rend l'auxiliaire lui-même infaisable, et ses duaux ne veulent plus
rien dire.

Le vecteur a une entrée par ligne de \(A\). Croisé avec `origines`, il devient un
libellé métier : `separation horizontale a|b`, `contour droit b`.

## Equalities and exact verification (batch 1.5c)

**Equalities are relaxed too.** The auxiliary problem relaxes each row of \(A_{eq}\)
(tiling, fusions, frozen contacts) with two slacks. Before, a conflict among those
equalities left it without an optimum and the certificate empty: 68 of 200 noisy
benchmark plans were refused with "origines non renseignees". Each equality now carries
a label (`Polytope.origines_eq`), and the refusal names every row with a non-zero weight.

**The certificate is checked, not believed.** Let \(y \ge 0\) be the multipliers of
\(Ax \le b\) and \(z\) those of \(A_{eq}x = b_{eq}\). Every admissible \(x\) satisfies

\[
r^\top x \le \beta, \qquad r = A^\top y + A_{eq}^\top z, \qquad
\beta = b^\top y + b_{eq}^\top z .
\]

With bounds \(l \le x \le u\),
\(\min_{l \le x \le u} r^\top x = \sum_j \min(r_j l_j, r_j u_j)\). If this minimum exceeds
\(\beta\), no admissible \(x\) exists. `certify.farkas.verify_infeasibility` computes it
in exact rational arithmetic (a float multiplier is an exact rational), so a verified
certificate is a proof even if the solver rounded; a noisy one can fail to verify, never
verify a feasible system. On the noisy benchmark, 88 of 89 certificates verify.

**Scope.** The certificate proves that the polytope of **this relative order** is empty.
Another order might admit a valid plan: `Infaisable` and `is_feasible` say so.

**Tightened domains.** The area cutting loop tightens variable bounds, which is not an
outer approximation; an infeasible verdict on a tightened domain said nothing about the
real problem (8 occurrences on the benchmark). The loop now solves the original domain
before concluding.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| `depart=` pour réutiliser le modèle (même polytope, nouvel objectif) | Réutiliser le cache si des *coupes* ont été ajoutées — le système a changé |
| Lire `Infaisable.origines`, pas seulement le message | Traduire un dual par « ligne 47 » |
| Distinguer `infaisable` / `non_borne` / `limite` | Fusionner en un booléen « pas optimal » |

## Source

- Bertsimas & Tsitsiklis (1997), ch. 4 — dualité et Farkas.
- Schrijver (1986), §7.3 — lemme de Farkas.
- Kelley (1960) — les coupes invalident la base, d'où le refus de cache.

[Bibliographie](sources.md).
