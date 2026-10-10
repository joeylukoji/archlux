# Import a DXF or IFC drawing

`Plan.from_dxf` reads a plan drawn in a CAD program, and `Structure.from_dxf` its
load-bearing structure. Both need the extra `cad`: `pip install "archlux[cad]"`.

## The drawing conventions

- **Rooms** are closed polylines on a layer (`ROOMS` by default), each an axis-aligned
  rectangle. An L-shaped room, a rotated one or an arc segment is refused with the
  handle of the entity, never approximated.
- **The type** of a room is the `TEXT` or `MTEXT` label inside it: `Living room` reads
  as `living_room`. A room without a label is refused unless you pass `default_type`.
- **Walls** are `LINE` entities or polyline sides: partitions on `wall_layer`,
  load-bearing walls on `load_bearing_layer`. **Columns** are `POINT` entities and
  `CIRCLE` centers on the structure layer.
- **Units** come from the `$INSUNITS` header (millimetres are converted to metres); a
  unitless drawing reads as metres, unless `scale` gives the metres per drawing unit.

Layer names compare without case, as in every CAD program. Block references are not
expanded: explode them first.

## Draw a two-room flat

The drawing is built here with `ezdxf`, in millimetres; in practice it comes from your
CAD program.

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

## Read and legalize it

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

Rooms are named `<type>-<n>`, numbered bottom to top, then left to right. The outline is
the rooms' bounding box unless `outline_layer` names a layer holding one closed
polyline.

## From an IFC model

`Plan.from_ifc` and `Structure.from_ifc` read one floor of a BIM model (extra `bim`:
`pip install "archlux[bim]"`). Without a geometry kernel, only footprints computable
exactly are accepted: a space whose `FootPrint` polyline, or whose vertical `Body`
extrusion of a rectangle or straight profile, is an axis-aligned rectangle once placed.
The type of a room is its `LongName`, else its `ObjectType`; its identifier is its
`Name` when all are distinct. A wall is load-bearing when `Pset_WallCommon.LoadBearing`
is true, and needs an `Axis` polyline; columns are `IfcColumn` origins. A model with
spaces on several storeys needs `storey="..."`. Units come from the project.

`Plan.to_ifc` writes `LoadBearing` on every wall, so an exported plan reads back with
its structure:

```python
with_walls = ax.Plan.from_dxf("flat.dxf", load_bearing_layer="LOAD_BEARING")
with_walls.to_ifc("flat.ifc")
again = ax.Plan.from_ifc("flat.ifc")
assert again.rooms == with_walls.rooms
print([(wall.id, wall.load_bearing) for wall in ax.Structure.from_ifc("flat.ifc").load_bearing_walls])
```

```text
[('load-bearing-1', True)]
```

## From the command line

`archlux legalize`, `verify` and `feasible` read a `.dxf` file directly, with the
default layers `ROOMS`, `WALLS` and `LOAD_BEARING`:

```bash
archlux verify flat.dxf --min-area living_room=14 --min-area bedroom=9
```
