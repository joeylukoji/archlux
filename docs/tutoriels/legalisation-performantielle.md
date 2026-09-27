# Légalisation performantielle

Après la [légalisation classique](premiers-pas.md), on peut choisir, *parmi les
plans valides de même ordre*, celui que le substitut juge le plus lumineux.

## Problème

Le correcteur L1 ignore l'orientation. Deux appartements identiques, nord et
sud, reçoivent la même correction. On veut préférer la lumière **sans** sortir
du polytope.

## Solution

```python
import archlux as ax
from archlux.light.analytique import AnalyticSurrogate

outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    rooms=(
        ax.Room(id="living_room", type="living_room", x=0.0, y=0.0, w=7.0, h=9.0),
        ax.Room(id="bedroom", type="bedroom", x=6.0, y=0.0, w=6.0, h=9.0),
    ),
    walls=(),
    openings=(),
    outline=outline,
)
ctx = ax.Context(
    structure=ax.Structure(()),
    orientation=ax.Orientation(0.0),
    outline=outline,
    regulation=ax.Regulation((), 1.0),
)

q = ax.legalize(plan, ctx, objective=AnalyticSurrogate())
assert q.certificate.geometry.valid
assert q.certificate.performance is None  # borne via certify.borne, pas via api
```

Le substitut analytique n'apprend rien : profondeur utile, table à 8 secteurs,
placement vers le sud. Il sert à valider le flux (polytope → Frank-Wolfe →
preuve) avant toute simulation.

`objective=None` (défaut) reste strictement le jalon 2. Un objet qui n'implémente
pas `Surrogate` lève `TypeError`.

## Ce qu'il faut retenir

Le réseau (`LearnedSurrogate`) est le [jalon 4](entrainer-un-substitut.md).
La borne conforme s'attache après calibration :
[calibrer un substitut](calibrer-un-substitut.md).
Comparer les méthodes avec `bench.compare(..., evaluate_by=oracle)` — jamais
avec le substitut lui-même.

**Voir aussi :** [Comparer deux méthodes](../galerie/02-comparer-deux-methodes.md),
[Oracle partagé](../concepts/oracle-partage.md).
