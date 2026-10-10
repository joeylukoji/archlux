# Command line

The `archlux` command runs the three main operations on a plan file (the
`Plan.to_json` format), without writing Python. The repository ships three plans to try
it on, in `examples/`.

## The context comes from the plan and the options

A plan file carries no context, so the command builds one: the plan's walls marked
`load_bearing` are the structure, its outline is the site, and the regulation comes from
`--min-width` (metres) and `--min-area TYPE=M2` (repeatable). `--orientation` gives
the azimuth in degrees.

## Verify a plan

```bash
archlux verify examples/t2.json --min-width 0.90 --min-area bedroom=9
```

```text
invalid
  NO  rooms overlap
  ok  no gap
  ok  minimum areas met
  ok  minimum widths met
  ok  structure kept
  - overlap bedroom|living: 0.36 m² (exact)
  - overlap bathroom|living: 0.2 m² (exact)
  max displacement: 0.000 m
```

The exact check covers overlaps, gaps, minimum areas and the load-bearing structure. The
command line adds the width check: every room rectangle, including each sub-rectangle of
an L-shaped room, must be at least `--min-width` wide in both directions, the same
bound the legalization enforces. A narrow room is named, for example
`width corridor: 0.50 m < 0.90 m`.

## Legalize it

```bash
archlux legalize examples/t2.json --tiling --min-width 0.90 -o fixed.json --svg fixed.svg --report
archlux verify fixed.json --min-width 0.90 --min-area bedroom=9
```

`-o` writes the repaired plan (it may overwrite the input), `--svg` a drawing, and
`--report` prints the same verdict for the result, or says that it carries no
certificate. `--tiling` also closes the gaps, so the rooms tile the outline.

## Ask whether the program is feasible

```bash
archlux feasible examples/t2.json --min-width 0.90 --min-area bedroom=9
```

## Exit codes and rejected options

| Code | Meaning |
|---|---|
| 0 | valid, feasible, or legalized |
| 1 | invalid or infeasible |
| 2 | error: unreadable file, rejected option, no valid plan found |

The three commands check their options the same way, before any computation:
`--min-width` and each `--min-area` value must be finite and non-negative; a
`--min-area` type must be one of the plan's room types (case-sensitive) and be given
once; `--orientation` must be finite and is taken modulo 360 (`-90` is `270`). A
rejected option prints one line and exits with code 2:

```text
archlux: error: --min-area: no room of type 'Bedroom' in the plan; its types are bathroom, bedroom, living_room
```
