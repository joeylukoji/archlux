# Pourquoi pas une image

Un relecteur formé à la vision par ordinateur demandera un CNN sur le plan
rasterisé. C'est le piège le plus séduisant du projet, et il le tue.

Déplacer un mur de 2 cm — exactement le geste de Frank-Wolfe — ne change
**aucun pixel** d'une image à résolution de pièce. Le gradient du réseau par
rapport aux variables de décision \(x,y,w,h\) est alors nul presque partout.
L'oracle linéaire reçoit \(c=0\), et l'optimiseur est aveugle.

L'entrée du substitut est donc un **ensemble de jetons** continus en géométrie
(`light.jetons.plan_vers_jetons`). Le test anti-image
(`test_jetons_continus`) échoue si un déplacement de 2 cm laisse les jetons
invariants.

`ARCHITECTURE.md` §10 en fait un anti-pattern fatal. Ce n'est pas une
préférence d'implémentation.
