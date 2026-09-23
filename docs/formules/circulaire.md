# Statistiques circulaires

**Code :** `orient.circulaire`.

## Énoncé

Un azimut \(\theta\) est un point du cercle. On l'encode par les harmoniques

\[
\phi(\theta)=\bigl(\cos\theta,\;\sin\theta,\;\cos 2\theta,\;\sin 2\theta,\;\ldots\bigr)
\in\mathbb{R}^{2H},
\]

jamais par le degré brut. La moyenne de \(n\) azimuts est l'argument de la
somme des vecteurs unitaires :

\[
\bar\theta=\operatorname{atan2}\Bigl(\sum_i\sin\theta_i,\;\sum_i\cos\theta_i\Bigr),
\qquad
\bar R=\frac{1}{n}\Bigl\lVert\textstyle\sum_i(\cos\theta_i,\,\sin\theta_i)\Bigr\rVert.
\]

La variance circulaire est \(V=1-\bar R\). Le test de Rayleigh d'uniformité
utilise \(p\approx\exp(-n\bar R^2)\).

## Hypothèses

- Angles en degrés à l'entrée, radians dans les fonctions trigonométriques.
- \(H\ge 1\). Une seule harmonique ne sépare pas l'est de l'ouest au-delà du signe de \(\sin\).
- Le test de Rayleigh est une approximation exponentielle (grand \(n\), ou
  concentration marquée). Pour \(n=5\) azimuts tous au nord, \(p<0{,}01\).

## Dérivation

\(359^\circ\) et \(1^\circ\) sont proches : \(\cos 359^\circ\approx\cos 1^\circ\).
La moyenne arithmétique \((359+1)/2=180\) est l'antipodale — le piège que
`moyenne_circulaire([350, 10])` doit éviter (résultat \(0^\circ\)).

La régression circulaire-linéaire est le moindre carré

\[
y\approx a\cos\theta+b\sin\theta+c.
\]

## Code

`encode`, `encoder`, `moyenne_circulaire`, `concentration`, `variance_circulaire`,
`rayleigh`, `regression_circulaire_lineaire`, `stratifier`.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Passer tout azimut par `encoder` avant un modèle | Soustraire des degrés comme des réels |
| Stratifier une rose des vents en 8 secteurs | Croire qu'un \(p\) de Rayleigh *prouve* une cause physique |

## Source

Mardia & Jupp (2000), *Directional Statistics*, Wiley, ch. 2–3 et §6.3 (Rayleigh).
[Bibliographie](sources.md) n° 11.
