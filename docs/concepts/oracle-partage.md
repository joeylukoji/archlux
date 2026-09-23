# L'oracle partagé

L'oracle linéaire de Frank-Wolfe **est** le solveur de légalisation. Ce n'est
pas une métaphore : c'est le même appel, avec un autre vecteur de coûts.

```python
# légalisation classique — jalon 2
sol = lmo.resoudre(poly, c=gradient_distance(Q_propose))

# une itération Frank-Wolfe — jalon 3
sol = lmo.resoudre(poly, c=-substitut.gradient(Q, orientation), depart=Q)
```

`lmo` ignore d'où vient \(c\). Cette ignorance est le cœur de
`ARCHITECTURE.md` : un seul simplexe, deux usages. Ajouter un second solveur
« pour la lumière » casserait la garantie que tout itéré est un plan valide.

Le démarrage à chaud (`depart=x` **à chaque** itération) ne change pas la
solution, seulement le temps. L'omettre dans une boucle de 50 tours coûte un
facteur 3 à 5.

La géométrie reste **exacte** (chaque itéré \(\in P\)). Le score du substitut
reste **sans garantie** jusqu'à la prédiction conforme (jalon 5). Ne pas
écrire « plan optimal pour la lumière » : écrire « plan valide qui maximise
le substitut, gap d'optimisation \(g\) ».

Voir [Frank-Wolfe](../formules/frank-wolfe.md),
[comparer deux méthodes](../galerie/02-comparer-deux-methodes.md).
