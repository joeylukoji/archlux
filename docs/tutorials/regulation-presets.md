# Regulation presets

Instead of typing the thresholds yourself, start from a **preset**: a regulation whose
every value cites the text it comes from, and which lists the rules of those texts that
the model cannot check.

!!! warning "A sourced aid, not legal advice"
    A preset reflects the texts as read on its `checked_on` date. Check the version in
    force, and your departmental health regulation (RSD), before relying on it.

## `fr/new-collective-housing`

New collective housing in France.

| Threshold | Source |
|---|---|
| living room ≥ 9 m² | Décret n° 2002-120 du 30 janvier 2002 (logement décent), art. 4 |
| bedroom ≥ 7 m² | Règlement sanitaire départemental type, art. 40.1 |
| every room at least 0.90 m wide | Arrêté du 24 décembre 2015 (accessibilité, construction neuve), art. 11: interior circulations |

The model knows minimum areas per room type and one minimum width. It does **not**
check, among others: the ceiling height (2.20 m) or the volume (20 m³), parts of a room
narrower than 2 m left out of its area, door widths, the clearances around a bed or the
turning circle of a shower room, nor a stricter departmental RSD. The preset lists them
in `not_checked`.

## Use it

```python
import archlux as ax

fr = ax.preset("fr/new-collective-housing")
for source in fr.sources:
    print(f"{source.rule:22} {source.text}")
print(len(fr.not_checked), "rules not checked")

plan = ax.Plan(
    rooms=(
        ax.Room(id="living", type="living_room", x=0.0, y=0.0, w=2.5, h=3.0),
        ax.Room(id="bed", type="bedroom", x=2.5, y=0.0, w=3.5, h=3.0),
    ),
    outline=((0.0, 0.0), (6.0, 0.0), (6.0, 3.0), (0.0, 3.0)),
)
ctx = ax.Context(ax.Structure(()), ax.Orientation(0.0), fr.regulation, outline=plan.outline)
fixed = ax.legalize(plan, ctx)
print({room.id: round(room.w * room.h, 2) for room in fixed.rooms})
```

```text
living_room >= 9 m2    Décret n° 2002-120 du 30 janvier 2002 (logement décent), article 4
bedroom >= 7 m2        Règlement sanitaire départemental type (circulaire du 9 août 1978), article 40.1
min_width >= 0.90 m    Arrêté du 24 décembre 2015 (accessibilité des bâtiments d'habitation collectifs lors de leur construction), article 11
6 rules not checked
{'living': 9.0, 'bed': 9.0}
```

The living room grows from 7.5 m² to 9 m², taken from the bedroom, which stays above
7 m².

## From the command line

```bash
archlux verify plan.json --preset fr/new-collective-housing
```

`--min-width` and `--min-area TYPE=M2` override the preset, type by type.
