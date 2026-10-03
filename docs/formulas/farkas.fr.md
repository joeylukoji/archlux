# Simplexe, duaux et Farkas

**Code :** `lmo.solver.solve`, `_certificat_farkas`, `_is_feasible`.

## Énoncé — primal

\[
\min_x \; c^\top x
\quad\text{s.c.}\quad
Ax \le b,\quad
A_{\mathrm{eq}} x = b_{\mathrm{eq}},\quad
\ell \le x \le u,
\]

plus les [coupes](area-cuts.md) \(\sum_j \alpha_j x_j \ge \beta\).

**Ce module ne sait pas d'où vient \(c\).** Distance L1 ou \(-\nabla\) d'éclairement :
même oracle (`ARCHITECTURE.md` §2).

Backend : OR-Tools **GLOP** (simplexe).

## Duaux

Si `duals=True`, les prix sont extraits **dans l'ordre des lignes de \(A\)** — le
seul ordre appariable avec `Polytope.origins`. Les coupes et les égalités ne sont
pas dans ce vecteur au jalon 2 : un dual de coupe de surface n'est pas encore
libellé. Les composantes \(\lvert y_i\rvert \le 10^{-9}\) sont omises à l'API.

Un prix dual se lit : « relâcher cette contrainte d'un mètre change l'objectif de
\(y_i\) ». C'est la dualité LP standard (Bertsimas & Tsitsiklis, ch. 4).

## Infeasible vs non borné

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

Le vecteur a une entrée par ligne de \(A\). Croisé avec `origins`, il devient un
libellé métier : `separation horizontale a|b`, `contour droit b`.

## Égalités et vérification exacte (lot 1.5c)

**Les égalités sont relâchées elles aussi.** Le problème auxiliaire relâche chaque ligne
de \(A_{eq}\) (pavage, fusions, contacts figés) avec deux variables d'écart. Auparavant,
un conflit entre ces égalités le laissait sans optimum et le certificat vide : 68 des 200
plans bruités du banc étaient refusés avec `origines non renseignees`. Chaque égalité
porte désormais un libellé (`Polytope.origins_eq`), et le refus nomme chaque ligne de
poids non nul.

**Le certificat est vérifié, pas cru.** Soit \(y \ge 0\) les multiplicateurs de
\(Ax \le b\) et \(z\) ceux de \(A_{eq}x = b_{eq}\). Tout \(x\) admissible vérifie

\[
r^\top x \le \beta, \qquad r = A^\top y + A_{eq}^\top z, \qquad
\beta = b^\top y + b_{eq}^\top z .
\]

Avec les bornes \(l \le x \le u\),
\(\min_{l \le x \le u} r^\top x = \sum_j \min(r_j l_j, r_j u_j)\). Si ce minimum dépasse
\(\beta\), aucun \(x\) admissible n'existe. `certify.farkas.verify_infeasibility` le
calcule en arithmétique rationnelle exacte (un multiplicateur flottant est un rationnel
exact) : un certificat vérifié est donc une preuve même si le solveur a arrondi ; un
certificat bruité peut échouer à la vérification, jamais valider un système faisable.
Sur le banc bruité, 88 certificats sur 89 sont vérifiés.

**Portée.** Le certificat prouve que le polytope de **cet ordre relatif** est vide. Un
autre ordre pourrait admettre un plan valide : `Infeasible` et `is_feasible` le disent.

**Domaines resserrés.** La boucle de coupes de surface resserre les bornes des
variables, ce qui n'est pas une approximation extérieure ; un verdict d'infaisabilité
sur un domaine resserré ne disait rien du problème réel (8 occurrences sur le banc). La
boucle résout désormais le domaine d'origine avant de conclure.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| `start=` pour réutiliser le modèle (même polytope, nouvel objectif) | Réutiliser le cache si des *coupes* ont été ajoutées — le système a changé |
| Lire `Infeasible.origins`, pas seulement le message | Traduire un dual par « ligne 47 » |
| Distinguer `infaisable` / `non_borne` / `limite` | Fusionner en un booléen « pas optimal » |

## Source

- Bertsimas & Tsitsiklis (1997), ch. 4 — dualité et Farkas.
- Schrijver (1986), §7.3 — lemme de Farkas.
- Kelley (1960) — les coupes invalident la base, d'où le refus de cache.

[Bibliographie](sources.md).
