# Les deux garanties

Un certificat `archlux` porte **deux affirmations de natures différentes**. Les
confondre — présenter une prédiction avec l'assurance d'une preuve — est la faute
que le système est conçu pour rendre difficile.

## Ce que dit le certificat

| | Géométrie | Performance lumineuse |
|---|---|---|
| **Phrase type** | « ce plan n'a aucun chevauchement » | « ce plan atteindra au moins 51,4 % » |
| **Nature** | Preuve | Prédiction assortie d'une marge |
| **Vérification** | Inspection finie, \(O(n^2)\) | Couverture \(\ge 1-\alpha\) sur un jeu de calibration |
| **Peut être fausse ?** | Non (à la tolérance d'arrondi près) | Oui, dans au plus \(\alpha\) des cas |
| **Type** | `PreuveGeometrique` — aucun champ de probabilité | `BornePerformance` — `couverture`, `n_calibration` et `regime` obligatoires |
| **Bandeau** | `[EXACT]` | `[PREDICTION — couverture 90 %]` (plan échangeable) ou `[PREDICTION — plan selectionne, couverture NON garantie]` |

La géométrie est un prédicat sur des rectangles : on peut le recompter. La lumière
est un oracle **gelé** (`SimulateurExact`, split-flux BRE) : la borne dit « au moins
neuf fois sur dix, la valeur de *cet* oracle tombera au-dessus du seuil annoncé ».
Ce n'est pas un sDA LM-83, ce n'est pas Radiance.

## Comment les lire l'une à côté de l'autre

```
GEOMETRIE                                       [EXACT]
  Chevauchement          aucun         verifie

PERFORMANCE                        [PREDICTION — couverture 90 %]
  sDA   >= 51,40   (predit 56,20, marge 4,80)
  calibration : 1284 évaluations de l'oracle gelé

NON EVALUABLE
  Confort d'été, systèmes techniques, matériaux — hors périmètre
```

- Si `performance is None`, la section prédiction affiche `NON EVALUABLE` : le
  système refuse d'inventer une couverture.
- `n_calibration` est affiché : une borne sur 50 points n'en vaut pas une sur 1 284.
- Le **régime** est affiché. La couverture n'est annoncée que pour un plan
  échangeable avec la calibration (`regime="exchangeable"`). Pour un plan choisi par
  l'optimiseur (`regime="selected"`, ce que rend `legalize(..., calibration=...)`),
  le bandeau dit « couverture NON garantie » et le rapport demande de réévaluer le
  plan avec l'oracle.
- Rien n'agrège les deux natures en un score unique.

## Ce qu'il faut retenir

La légalisation **prouve** que le plan est un pavage valide. Le substitut
**prévoit** un indicateur et le calibrateur **borne** cette prévision. Le lecteur
qui lit « 51,4 % » comme il lit « aucun chevauchement » se trompe de garantie.

**Voir aussi :** [Prédiction conforme](prediction-conforme.md),
[Lire un certificat](../galerie/04-lire-un-certificat.md),
[Limites](../limites.md).
