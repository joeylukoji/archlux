"""Input and output: the versioned JSON schema, and DXF reading (PLAN.md 5.1).

The package re-exports what the facades of :mod:`archlux.types` call (``Plan.from_json``,
``to_json``, ``from_dxf``, ``Structure.from_dxf``): their single exemption to the layer
rule names the package, not each module (ADR-5).
"""

from archlux.io.dxf_io import load_plan, load_structure
from archlux.io.json_io import load, write

__all__ = ["load", "load_plan", "load_structure", "write"]
