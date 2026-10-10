# Préréglages réglementaires

Au lieu de saisir les seuils vous-même, partez d'un **préréglage** : une réglementation
dont chaque valeur cite le texte d'où elle vient, et qui liste les règles de ces textes
que le modèle ne sait pas vérifier.

!!! warning "Une aide sourcée, pas un avis juridique"
    Un préréglage reflète les textes tels que lus à sa date `checked_on`. Vérifiez la
    version en vigueur, et votre règlement sanitaire départemental (RSD), avant de vous
    y fier.

## `fr/new-collective-housing`

Logement collectif neuf en France.

| Seuil | Source |
|---|---|
| séjour ≥ 9 m² | Décret n° 2002-120 du 30 janvier 2002 (logement décent), art. 4 |
| chambre ≥ 7 m² | Règlement sanitaire départemental type, art. 40.1 |
| toute pièce large d'au moins 0,90 m | Arrêté du 24 décembre 2015 (accessibilité, construction neuve), art. 11 : circulations intérieures |

Le modèle connaît des surfaces minimales par type de pièce et une largeur minimale. Il
ne vérifie **pas**, entre autres : la hauteur sous plafond (2,20 m) ou le volume
(20 m³), les parties d'une pièce de moins de 2 m de large exclues de sa surface, les
largeurs de portes, les espaces libres autour du lit ou l'aire de rotation de la salle
d'eau, ni un RSD départemental plus strict. Le préréglage les liste dans `not_checked`.

## L'utiliser

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

Le séjour passe de 7,5 m² à 9 m², pris sur la chambre, qui reste au-dessus de 7 m².

## En ligne de commande

```bash
archlux verify plan.json --preset fr/new-collective-housing
```

`--min-width` et `--min-area TYPE=M2` remplacent le préréglage, type par type.
