# Vérification exacte

**Code :** `certify.proof.verify_exactly`.

Indépendante du solveur : si GLOP a un bogue, c'est cette inspection qui le
montre (`ARCHITECTURE.md` : ne jamais croire le solveur).

## Énoncé

Quatre prédicats, conjonction pour `valide`. **Aucun n'est probabiliste.**

\[
\mathrm{valide}
 = \neg\mathrm{chevauchement}
 \land \neg\mathrm{jours}
 \land \mathrm{surfaces\_ok}
 \land \mathrm{structure\_preservee}.
\]

### Chevauchement

Pour chaque paire de rectangles \(R_i,R_j\), aire d'intersection
\(\lambda(R_i\cap R_j)\) (GEOS / Shapely, clipping de Vatti, 1992). Chevauchement
ssi cette aire dépasse \(10^{-9}\,\mathrm{m}^2\). Messages en virgule française :
`"chevauchement cuisine|sdb : 0,03 m²"`. Complexité \(O(n^2)\) paires, assumée.

### Jours

Soit \(U=\bigcup_i R_i\) et \(C\) le polygone du contour. Un jour existe ssi

\[
\bigl\lvert \lambda(U)-\lambda(C)\bigr\rvert > \tau,
\qquad \tau=10^{-6}\,\mathrm{m}^2.
\]

Un pavage exact vérifie \(\lambda(U)=\lambda(C)\) et \(\lambda(R_i\cap R_j)=0\)
pour \(i\neq j\) (additivité de Lebesgue sur une union disjointe, Halmos, 1950).

Ce test est plus fort que « pas de trou intérieur » : un plan qui ne *remplit*
pas l'enveloppe est rejeté. Le [L1](epigraphe-l1.md) ne force pas le remplissage ;
`legalize` ne promet un pavage que si l'entrée en est déjà un (guillotine) ou si
l'union des pièces recouvre \(C\) (chevauchement à corriger sans créer de jour).

### Surfaces

\[
w_p h_p \ge a_{\min}(\mathrm{type}(p))
\]

pour chaque pièce, à \(10^{-9}\,\mathrm{m}^2\) près. \(a_{\min}=0\) si le type
est inconnu (`Referentiel.a_min`).

### Structure

No room crosses a load-bearing wall of `ctx.structure`: for every wall segment
\(S\) and room \(R\),

\[
\operatorname{length}\bigl(S \cap \operatorname{int}_{\varepsilon}(R)\bigr) \le \varepsilon,
\qquad \varepsilon = 10^{-7}\,\mathrm{m},
\]

where \(\operatorname{int}_{\varepsilon}(R)\) is the room shrunk by \(\varepsilon\) on every
side, so that a room *bounded* by the wall is accepted. The test is geometric and holds
for oblique walls. A wall declared in the plan with the same `id` must also match the
structure (same end points, order irrelevant). Columns are not checked.

*Before 0.10 this predicate only compared each wall with itself (walls are not decision
variables), so it was always true (AUDIT.md §3 n°1).*

### Déplacement

Norme \(\ell_\infty\) sur les quatre cotes, max sur les pièces de même `id` :

\[
\delta_\infty
 =\max_p \max\bigl(\lvert\Delta x\rvert,\lvert\Delta y\rvert,
 \lvert\Delta w\rvert,\lvert\Delta h\rvert\bigr)
 \quad[\mathrm{m}].
\]

`reference=None` rend \(0\).

## Exact rational proof of the tiling (rectangular outlines)

Since batch 1.5b, when the outline is an axis-aligned rectangle \(C\), overlaps and
gaps are no longer decided by GEOS areas with tolerances, but proved in exact rational
arithmetic (`certify.proof.rational_tiling`):

1. **Identification.** Edge coordinates closer than \(\varepsilon = 10^{-7}\) m
   (`SNAP_M`) are identified, each group being anchored on its smallest value. This is
   the **only** tolerance: it applies to lengths, whatever the size of the rooms, and
   absorbs both decimal inputs (\(0.1 + 0.2 \ne 0.3\) in binary floating point) and the
   LP noise.
2. **Exact check.** Every coordinate is then an exact `Fraction` (a binary float is an
   exact rational) and three conditions are tested with no tolerance: (i) every room
   lies in \(C\); (ii) the interiors of any two rooms are disjoint; (iii)
   \(\sum_i \lambda(R_i) = \lambda(C)\).

**Theorem.** (i) and (ii) give
\(\lambda(\bigcup_i R_i) = \sum_i \lambda(R_i) \le \lambda(C)\); with (iii), the part of
\(C\) left uncovered has measure \(\lambda(C) - \sum_i \lambda(R_i) = 0\). The rooms tile
\(C\) up to a null set: no gap, no overlap.

When rooms overlap, (iii) no longer measures coverage; the gap diagnosis then comes from
GEOS, so that the report stays complete (the plan is invalid either way). Outlines that
are not rectangles keep the GEOS area checks and their tolerances.

**Measured agreement.** On 800 plans of the guarantee benchmark (valid, corrupted, noisy
and legalized), the rational proof and the former GEOS check give identical overlap and
gap verdicts. The certification of 15 rooms takes about 0.8 ms (1.5 ms with GEOS).

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Appeler *après* le solveur, sur le plan dévectorisé | Réutiliser les duaux ou `poly.contient` comme preuve utilisateur |
| Rapporter **toutes** les violations | S'arrêter à la première |
| Mettre un champ de probabilité dans `PreuveGeometrique` | — interdit : la thèse du projet est dans ce type |

## Source

- Vatti (1992), *CACM* — clipping, [doi:10.1145/129902.129906](https://doi.org/10.1145/129902.129906).
- Halmos (1950), *Measure Theory* — additivité.
- La norme \(\lVert\cdot\rVert_\infty\) est la définition usuelle ; pas un théorème.

[Bibliographie](sources.md).
