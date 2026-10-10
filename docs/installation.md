# Installation

```bash
pip install archlux                # core: no learning dependency
pip install "archlux[appris]"      # + trained surrogate (torch)
pip install "archlux[ml]"          # alias of ``appris``
pip install "archlux[cad]"         # + DXF reading (ezdxf)
pip install "archlux[bim]"         # + IFC reading and validation (ifcopenshell)
# ``archlux[sim]``: empty extra (Radiance). Off the critical path; CI
# uses ``SplitFluxOracle`` (closed form).
```

Python 3.11 or later. The core never imports `torch`: `import archlux` stays
light, even with the extra installed.
