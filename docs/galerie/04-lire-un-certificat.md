# Lire un certificat

**Problème.** Le solveur a rendu un plan valide. On veut savoir, sur une page,
ce qui est **prouvé** et ce qui est **prédit** — sans les mélanger.

**Solution.**

```python
import archlux as ax
from archlux.types import BornePerformance, Manifeste

contour = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    pieces=(
        ax.Piece(id="sejour", type="sejour", x=0.0, y=0.0, w=7.0, h=9.0),
        ax.Piece(id="chambre", type="chambre", x=6.0, y=0.0, w=6.0, h=9.0),
    ),
    murs=(),
    ouvertures=(),
    contour=contour,
)
ctx = ax.Contexte(
    structure=ax.Structure(murs_porteurs=()),
    orientation=ax.Orientation(deg=12.0),
    contour=contour,
    referentiel=ax.Referentiel(aires_min=(), largeur_min=1.0),
)
q = ax.legalize(plan, ctx)
borne = BornePerformance(
    indicateur="sDA",
    valeur=56.2,
    borne_inf=51.4,
    borne_sup=61.0,
    couverture=0.90,
    n_calibration=1284,
    regime="exchangeable",
)
certificat = ax.Certificat(
    geometrie=q.certificat.geometrie,
    performance=borne,
    duaux=q.certificat.duaux,
    manifeste=Manifeste(version="0.4.0", horodatage="2026-09-09T00:00:00Z", graine=17),
)
print(certificat.rapport())
```

On construit ici la borne à la main pour lire le gabarit. `regime="exchangeable"`
déclare que le plan est échangeable avec le jeu de calibration (un plan tenu à
l'écart, par exemple) : c'est le seul cas où la couverture de 90 % est garantie.
`legalize(..., objective=..., calibration=...)` attache lui-même la borne, mais en
régime `"selected"` : l'optimiseur a choisi le plan, et le rapport écrit alors
`[PREDICTION — plan selectionne, couverture NON garantie]`.

**Résultat.** Le texte sépare `[EXACT]` et `[PREDICTION — couverture 90 %]`.
`n_calibration` (1 284) est visible. La section `NON EVALUABLE` est toujours
là : confort d'été, systèmes, matériaux.

**Ce qu'il faut retenir.** « Aucun chevauchement » se revérifie en comptant des
aires. « sDA ≥ 51,4 » est une couverture à 90 % **contre l'oracle gelé**
(split-flux), pas un sDA réglementaire. Si `performance is None`, le rapport
écrit `NON EVALUABLE` dans la section prédiction plutôt que d'inventer un
chiffre.

**Voir aussi :** [Les deux garanties](../concepts/deux-garanties.md),
[Diagnostic dual](05-diagnostic-dual.md),
[Prédiction conforme](../concepts/prediction-conforme.md).
