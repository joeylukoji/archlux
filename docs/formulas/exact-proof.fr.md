# Vérification exacte

**Code :** `certify.proof.verify_exactly`.

Indépendante du solveur : si GLOP a un bogue, c'est cette inspection qui le
montre (`ARCHITECTURE.md` : ne jamais croire le solveur).

## Énoncé

Quatre prédicats, conjonction pour `valid`. **Aucun n'est probabiliste.**

\[
\mathrm{valid}
 = \neg\mathrm{overlap}
 \land \neg\mathrm{gaps}
 \land \mathrm{areas\_ok}
 \land \mathrm{structure\_kept}.
\]

### Chevauchement

Pour chaque paire de rectangles \(R_i,R_j\), aire d'intersection
\(\lambda(R_i\cap R_j)\) (GEOS / Shapely, clipping de Vatti, 1992). Chevauchement
ssi cette aire dépasse `OVERLAP_M2` \(=10^{-9}\,\mathrm{m}^2\). Message :
`"overlap kitchen|bathroom: 0.0300 m²"`. Complexité \(O(n^2)\) paires, assumée. Ce chemin
GEOS ne sert plus qu'aux contours non rectangulaires ; un contour rectangulaire passe
par la preuve rationnelle ci-dessous.

### Jours

Soit \(U=\bigcup_i R_i\) et \(C\) le polygone du contour. Un jour existe ssi

\[
\bigl\lvert \lambda(U)-\lambda(C)\bigr\rvert > \tau,
\qquad \tau=10^{-6}\,\mathrm{m}^2.
\]

Un pavage exact vérifie \(\lambda(U)=\lambda(C)\) et \(\lambda(R_i\cap R_j)=0\)
pour \(i\neq j\) (additivité de Lebesgue sur une union disjointe, Halmos, 1950).

Ce test est plus fort que « pas de trou intérieur » : un plan qui ne *remplit*
pas l'enveloppe est rejeté. Le [L1](l1-epigraph.md) ne force pas le remplissage ;
`legalize` ne promet un pavage que si l'entrée en est déjà un (guillotine) ou si
l'union des pièces recouvre \(C\) (chevauchement à corriger sans créer de jour).

### Surfaces

\[
w_p h_p \ge a_{\min}(\mathrm{type}(p))
\]

pour chaque pièce, à \(10^{-9}\,\mathrm{m}^2\) près. \(a_{\min}=0\) si le type
est inconnu (`Regulation.min_area`).

**Pièces fusionnées** (un L décomposé en sous-rectangles, `verify_exactly(..., merges=)`).
Le minimum s'applique à l'union \(U = \bigcup_k R_k\) des parties, jamais à chaque
partie : \(\lambda(U) \ge a_{\min}\). Avant la surface, chaque couture enregistrée par la
décomposition doit encore tenir : les deux parties se touchent le long de celle-ci
(décalage d'au plus `SNAP_M`) sur une longueur d'au moins `min_width` (moins `SNAP_M`),
le contact que le solveur impose (`geom.rectilinear.overlap_constraints`). La seule
connexité accepterait un pied qui aurait glissé sur un autre bord, ou un col de
\(10^{-7}\) m. Des parties qui ne forment pas un seul polygone par leurs bords
(détachées, ou se touchant en un coin) sont refusées.

### Structure

Aucune pièce ne traverse un mur porteur de `ctx.structure` : pour tout segment de mur
\(S\) et toute pièce \(R\),

\[
\operatorname{length}\bigl(S \cap \operatorname{int}_{\varepsilon}(R)\bigr) \le \varepsilon,
\qquad \varepsilon = 10^{-7}\,\mathrm{m},
\]

où \(\operatorname{int}_{\varepsilon}(R)\) est la pièce rétrécie de \(\varepsilon\) de
chaque côté, de sorte qu'une pièce *bordée* par le mur est acceptée. Une pièce fusionnée
n'a qu'un intérieur, \(\operatorname{int}_{\varepsilon}(\bigcup_k R_k)\) : un mur le long
de la couture entre deux parties coupe la pièce en deux et constitue une traversée, bien
qu'il soit sur le bord de chaque partie. Le test est géométrique et vaut pour les murs
obliques. Un mur déclaré dans le plan avec le même `id` doit aussi correspondre à la
structure (mêmes extrémités, ordre indifférent). Les poteaux ne sont pas vérifiés.

*Avant 0.10, ce prédicat ne comparait chaque mur qu'à lui-même (les murs ne sont pas des
variables de décision), il était donc toujours vrai (AUDIT.md §3 n°1).*

### Déplacement

Norme \(\ell_\infty\) sur les quatre cotes, max sur les pièces de même `id` :

\[
\delta_\infty
 =\max_p \max\bigl(\lvert\Delta x\rvert,\lvert\Delta y\rvert,
 \lvert\Delta w\rvert,\lvert\Delta h\rvert\bigr)
 \quad[\mathrm{m}].
\]

`reference=None` rend \(0\).

## Preuve rationnelle exacte du pavage (contours rectangulaires)

Depuis le lot 1.5b, lorsque le contour est un rectangle \(C\) aligné sur les axes, les
chevauchements et les jours ne sont plus décidés par des aires GEOS à tolérances, mais
prouvés en arithmétique rationnelle exacte (`certify.proof.rational_tiling`) :

1. **Identification.** Les coordonnées de bords plus proches que \(\varepsilon = 10^{-7}\) m
   (`SNAP_M`) sont identifiées, chaque groupe étant ancré sur sa plus petite valeur. C'est
   la **seule** tolérance : elle porte sur des longueurs, quelle que soit la taille des
   pièces, et absorbe à la fois les entrées décimales (\(0.1 + 0.2 \ne 0.3\) en virgule
   flottante binaire) et le bruit du PL.
2. **Vérification exacte.** Chaque coordonnée est alors une `Fraction` exacte (un
   flottant binaire est un rationnel exact) et trois conditions sont testées sans
   tolérance : (i) chaque pièce est dans \(C\) ; (ii) les intérieurs de deux pièces
   quelconques sont disjoints ; (iii) \(\sum_i \lambda(R_i) = \lambda(C)\).

**Théorème.** (i) et (ii) donnent
\(\lambda(\bigcup_i R_i) = \sum_i \lambda(R_i) \le \lambda(C)\) ; avec (iii), la partie
de \(C\) non couverte est de mesure \(\lambda(C) - \sum_i \lambda(R_i) = 0\). Les pièces
pavent \(C\) à un ensemble négligeable près : ni jour, ni chevauchement.

Quand des pièces se chevauchent, (iii) ne mesure plus la couverture ; le diagnostic des
jours vient alors de GEOS, pour que le rapport reste complet (le plan est invalide dans
tous les cas). Les contours non rectangulaires gardent les vérifications d'aire GEOS et
leurs tolérances.

**Ce que l'identification efface.** Le théorème porte sur les rectangles *identifiés*.
Déplacer des bords de moins de \(\varepsilon = \) `SNAP_M` peut masquer jusqu'à
\(\varepsilon\) fois un périmètre d'aire (9e-6 m² le long d'un bord de 100 m), plus que la
tolérance du vérificateur. Une fois le pavage identifié prouvé, le plan brut est donc
borné lui aussi, toujours en arithmétique exacte : chaque chevauchement brut par paire
\(\lambda(R_i \cap R_j) \le\) `OVERLAP_M2` ; le débord
\(\sum_i \lambda(R_i) - \lambda(R_i \cap C) \le\) `GAP_M2` ; et, par l'inégalité de
Bonferroni \(\lambda(\bigcup_i R_i \cap C) \ge \sum_i \lambda(R_i \cap C) - \sum_{i<j}
\lambda(R_i \cap R_j \cap C)\), la surface non couverte vaut au plus
\(\lambda(C) - \sum_i \lambda(R_i \cap C) + \sum_{i<j} \lambda(R_i \cap R_j \cap C) \le\)
`GAP_M2`. Ce sont les tolérances du chemin GEOS et du vérificateur des tests, si bien que
les deux chemins concordent sur tout plan, pas seulement sur le banc (revue du lot 1.5,
M2).

**Concordance mesurée.** Sur les plans du banc de garantie (valides, corrompus, bruités
et légalisés), la preuve rationnelle et la vérification GEOS rendent des verdicts
identiques de chevauchement et de jour. La certification de 15 pièces prend environ
0,8 ms (1,5 ms avec GEOS).

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Appeler *après* le solveur, sur le plan dévectorisé | Réutiliser les duaux ou `poly.contains` comme preuve utilisateur |
| Rapporter **toutes** les violations | S'arrêter à la première |
| Mettre un champ de probabilité dans `GeometricProof` | — interdit : la thèse du projet est dans ce type |

## Source

- Vatti (1992), *CACM* — clipping, [doi:10.1145/129902.129906](https://doi.org/10.1145/129902.129906).
- Halmos (1950), *Measure Theory* — additivité.
- La norme \(\lVert\cdot\rVert_\infty\) est la définition usuelle ; pas un théorème.

[Bibliographie](sources.md).
