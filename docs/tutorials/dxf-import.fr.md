# Importer un dessin DXF

`Plan.from_dxf` lit un plan dessiné dans un logiciel de CAO, et `Structure.from_dxf` sa
structure porteuse. Les deux demandent l'extra `cad` : `pip install "archlux[cad]"`.

## Les conventions de dessin

- **Les pièces** sont des polylignes fermées sur un calque (`ROOMS` par défaut), chacune
  un rectangle aligné sur les axes. Une pièce en L, une pièce tournée ou un segment
  d'arc est refusé avec la référence (handle) de l'entité, jamais approché.
- **Le type** d'une pièce est l'étiquette `TEXT` ou `MTEXT` placée à l'intérieur :
  `Living room` se lit `living_room`. Une pièce sans étiquette est refusée, sauf si
  `default_type` est donné.
- **Les murs** sont des entités `LINE` ou des côtés de polylignes : cloisons sur
  `wall_layer`, murs porteurs sur `load_bearing_layer`. **Les poteaux** sont des
  entités `POINT` et des centres de `CIRCLE` sur le calque de la structure.
- **Les unités** viennent de l'en-tête `$INSUNITS` (les millimètres sont convertis en
  mètres) ; un dessin sans unité se lit en mètres, sauf si `scale` donne le nombre de
  mètres par unité de dessin.

Les noms de calques se comparent sans tenir compte de la casse, comme dans tout logiciel
de CAO. Les références de blocs ne sont pas développées : décomposez-les d'abord.

## Dessiner un deux-pièces

Le dessin est construit ici avec `ezdxf`, en millimètres ; en pratique, il vient de
votre logiciel de CAO.

```python
import ezdxf

doc = ezdxf.new()
doc.units = ezdxf.units.MM
msp = doc.modelspace()
for x, w, label in ((0, 5000, "Living room"), (5000, 3000, "Bedroom")):
    corners = [(x, 0), (x + w, 0), (x + w, 4000), (x, 4000)]
    msp.add_lwpolyline(corners, close=True, dxfattribs={"layer": "ROOMS"})
    msp.add_text(label, dxfattribs={"layer": "ROOMS", "insert": (x + w / 2, 2000)})
msp.add_line((5000, 0), (5000, 4000), dxfattribs={"layer": "LOAD_BEARING"})
doc.saveas("flat.dxf")
```

## Le lire et le légaliser

```python
import archlux as ax

plan = ax.Plan.from_dxf("flat.dxf")
structure = ax.Structure.from_dxf("flat.dxf")
print([(room.id, room.w, room.h) for room in plan.rooms])

regulation = ax.Regulation(min_areas=(("living_room", 14.0), ("bedroom", 9.0)), min_width=0.9)
ctx = ax.Context(structure, ax.Orientation(0.0), regulation, outline=plan.outline)
fixed = ax.legalize(plan, ctx)
assert fixed.certificate is not None and fixed.certificate.geometry.valid
```

```text
[('living_room-1', 5.0, 4.0), ('bedroom-1', 3.0, 4.0)]
```

Les pièces sont nommées `<type>-<n>`, numérotées de bas en haut, puis de gauche à
droite. Le contour est la boîte englobante des pièces, sauf si `outline_layer` désigne
un calque portant une seule polyligne fermée.

## En ligne de commande

`archlux legalize`, `verify` et `feasible` lisent directement un fichier `.dxf`, avec
les calques par défaut `ROOMS`, `WALLS` et `LOAD_BEARING` :

```bash
archlux verify flat.dxf --min-area living_room=14 --min-area bedroom=9
```
