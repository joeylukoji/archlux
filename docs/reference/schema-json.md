# JSON schema of plans, version `2`

Exchange format read and written by `Plan.from_json` and `Plan.to_json`. Units: **metres**,
square metres, azimuth in degrees. Origin at the bottom-left corner of the outline, `y` axis
towards geographic north.

Schema **v2** has English keys and English room types. Files of schema **v1** (French keys
and room types) are still read: see [Reading schema v1](#reading-schema-v1).

## Rules of the format

- **The version is mandatory.** A file whose `schema` is neither `"2"` nor `"1"` is refused
  with `InvariantViolation`: better to refuse loudly than to guess the format, because a
  misread plan produces a false certificate.
- **Writing is deterministic.** Sorted keys, UTF-8, indentation 2, line ending `
`. Two
  writes of the same plan give the same bytes; without that, the fingerprint recorded in a
  manifest identifies nothing.
- **No absolute position of an opening.** An opening is described by `wall_id`, `s` and
  `relative_width`; its position is derived from the wall. That is the invariant that keeps
  windows and partitions from desynchronizing when the solver moves a wall.
- **An explicit `null` rather than an absent key.** `"performance": null` means "no
  performance guarantee claimed": information, not an oversight.
- **The ranges are checked at reading.** `s` in `[0, 1]`, `relative_width` in `]0, 1]`,
  strictly positive sizes and thicknesses, and **no non-finite value**, although
  `json.loads` accepts the literals `NaN` and `Infinity`. A faulty file is refused with the
  **complete list** of its violations, not only the first one.

## Published schema

The format is described by a **JSON Schema** (draft 2020-12) shipped with the package:
`archlux/io/plan-v2.schema.json` (and `plan-v1.schema.json` for the old format). A third
party can validate a file without running archlux:

```python
import json
from importlib import resources

import jsonschema

schema = json.loads(resources.files("archlux.io").joinpath("plan-v2.schema.json").read_text())
plan = {"schema": "2", "outline": [[0, 0], [4, 0], [4, 3], [0, 3]],
        "rooms": [{"id": "a", "type": "living_room", "x": 0, "y": 0, "w": 4, "h": 3}],
        "walls": [], "openings": [], "certificate": None}
jsonschema.validate(plan, schema)
```

The schema and the reader refuse the same ranges (test `test_json_schema.py`), with one
exception: JSON Schema cannot express "finite number", so only the reader refuses `NaN` and
`Infinity`. Every output of `Plan.to_json` is valid for the schema, certificate and `regime`
included.

## Fields

| Field | Type | Meaning |
|---|---|---|
| `schema` | `"2"` | Version of the format |
| `outline` | list of `[x, y]` | Envelope of the dwelling |
| `rooms[]` | `id`, `type`, `x`, `y`, `w`, `h` | Rectangle, bottom-left corner at `(x, y)` |
| `walls[]` | `id`, `a`, `b`, `load_bearing`, `thickness` | Segment; `load_bearing: true` means fixed by the solver |
| `openings[]` | `id`, `wall_id`, `s`, `relative_width`, `sill_height`, `head_height` | `s` = abscissa **of the center** along the wall, in `[0, 1]`; `relative_width` as a fraction of the wall length |
| `certificate` | object or `null` | `null` for a proposed plan; always present on a legalized plan |

The room `type` is free text. The values the library knows are `living_room`, `bedroom`,
`kitchen`, `bathroom`, `toilet` and `corridor`; any other type is kept as is and gets no
minimum area from a `Regulation` that does not list it.

### The certificate

Two guarantees of different kinds, separated by construction; see
[The two guarantees](../concepts/deux-garanties.md).

| Field | Kind | Meaning |
|---|---|---|
| `geometry` | **exact** | The four predicates verified independently of the solver (`overlap`, `gaps`, `areas_ok`, `structure_kept`), `valid` and `max_displacement` |
| `performance` | **probabilistic** | Conformal interval, with `coverage`, `n_calibration` and `regime` (`"exchangeable"` or `"selected"`, mandatory: a file without `regime` is refused). `coverage` is **nominal**: it is only guaranteed if `regime` is `"exchangeable"`. `null` in classic legalization |
| `duals` | diagnostic | Pairs `[label, cost]`: which constraint to relax, and what it costs |
| `manifest` | trace | Version, seed, fingerprints: what makes the run replayable |

`geometry` holds **no** probability field, and must never hold one.

## Complete example

A legalized flat, produced by `Plan.to_json` (not an example copied by hand):

```json
{
  "certificate": {
    "duals": [],
    "geometry": {
      "areas_ok": true,
      "gaps": false,
      "max_displacement": 0.21,
      "overlap": false,
      "structure_kept": true,
      "valid": true,
      "violations": []
    },
    "manifest": null,
    "performance": null
  },
  "openings": [
    {
      "head_height": 2.15,
      "id": "w1",
      "relative_width": 0.25,
      "s": 0.3,
      "sill_height": 1.0,
      "wall_id": "south"
    }
  ],
  "outline": [
    [
      0.0,
      0.0
    ],
    [
      6.0,
      0.0
    ],
    [
      6.0,
      3.5
    ],
    [
      0.0,
      3.5
    ]
  ],
  "rooms": [
    {
      "h": 3.5,
      "id": "living",
      "type": "living_room",
      "w": 4.0,
      "x": 0.0,
      "y": 0.0
    },
    {
      "h": 2.5,
      "id": "bath",
      "type": "bathroom",
      "w": 2.0,
      "x": 4.0,
      "y": 0.0
    }
  ],
  "schema": "2",
  "walls": [
    {
      "a": [
        0.0,
        0.0
      ],
      "b": [
        6.0,
        0.0
      ],
      "id": "south",
      "load_bearing": true,
      "thickness": 0.1
    }
  ]
}
```

> The outline and the points are written as nested lists; the real file puts one number per
> line, which makes Git differences readable point by point.

## Reading schema v1

A schema v1 file is read through an explicit upgrade (`archlux.io.json_io.upgrade_v1`), and
the writer only ever emits v2, so loading and saving a v1 file converts it.

| v1 (French) | v2 |
|---|---|
| `contour`, `pieces`, `murs`, `ouvertures`, `certificat` | `outline`, `rooms`, `walls`, `openings`, `certificate` |
| `porteur`, `epaisseur` | `load_bearing`, `thickness` |
| `mur_id`, `largeur_rel`, `hauteur_allege`, `hauteur_linteau` | `wall_id`, `relative_width`, `sill_height`, `head_height` |
| `geometrie`, `duaux`, `manifeste` | `geometry`, `duals`, `manifest` |
| `valide`, `chevauchement`, `jours`, `surfaces_ok`, `structure_preservee`, `deplacement_max` | `valid`, `overlap`, `gaps`, `areas_ok`, `structure_kept`, `max_displacement` |
| `indicateur`, `valeur`, `borne_inf`, `borne_sup`, `couverture` | `indicator`, `value`, `lower`, `upper`, `coverage` |
| `horodatage`, `graine`, `empreinte_donnees`, `decoupage`, `environnement`, `parametres`, `modele`, `poids` | `timestamp`, `seed`, `data_fingerprint`, `split`, `environment`, `parameters`, `model`, `weights_fingerprint` |
| room types `sejour`, `chambre`, `cuisine`, `sdb`, `wc`, `couloir` | `living_room`, `bedroom`, `kitchen`, `bathroom`, `toilet`, `corridor` |

The English room types apply to v1 files too: an unknown type passes through unchanged.

## Compatibility

A file written by an older release must stay readable by a newer one. Any incompatible
change increments `SCHEMA_VERSION` and gets an entry in the CHANGELOG; the previous format
is read through an upgrade function until a release announces its removal.
