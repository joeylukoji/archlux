# Vérification exacte

**Code :** `certify.preuve.verifier_exactement`.

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

Chaque mur porteur de `ctx.structure` apparaît dans le plan, même `id`, mêmes
extrémités à \(10^{-7}\,\mathrm{m}\) près (ordre des points indifférent).

### Déplacement

Norme \(\ell_\infty\) sur les quatre cotes, max sur les pièces de même `id` :

\[
\delta_\infty
 =\max_p \max\bigl(\lvert\Delta x\rvert,\lvert\Delta y\rvert,
 \lvert\Delta w\rvert,\lvert\Delta h\rvert\bigr)
 \quad[\mathrm{m}].
\]

`reference=None` rend \(0\).

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
