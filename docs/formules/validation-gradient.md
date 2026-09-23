# Validation du gradient

**Code :** `light.validation.valider_gradient`.

## Énoncé

Pour un point \(x\) et une direction \(e_i\), la pente réelle du simulateur est

\[
\widehat{\partial_i f}(x)
=\frac{f(x+\delta e_i)-f(x-\delta e_i)}{2\delta}.
\]

L'**accord de signe** est la fraction des coordonnées telles que
\(\mathrm{sign}(\nabla \hat f_i)=\mathrm{sign}(\widehat{\partial_i f})\).

| Accord | Décision |
|---|---|
| \(> 0{,}90\) | continuer |
| \(0{,}80\)–\(0{,}90\) | continuer en surveillant |
| \(< 0{,}80\) | **arrêt** — ne pas ouvrir le jalon 5 |

## Hypothèses

- Le simulateur est déterministe (sinon la pente n'est pas définie).
- \(\delta=0{,}10\,\mathrm{m}\) pour le point de contrôle (pas un \(\varepsilon\)
  numérique).
- On évalue par le simulateur, jamais par le réseau.

## Source

`MILESTONE-4.md` §7. Différences finies centrées : Nocedal & Wright,
*Numerical Optimization*, Springer, §8.1.
