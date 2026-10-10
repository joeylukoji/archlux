"""Input and output: the versioned JSON schema, and DXF and IFC reading (PLAN.md 5.1).

The package re-exports what the facades of :mod:`archlux.types` call (``Plan.from_json``,
``to_json``, ``from_dxf``, ``from_ifc``, ``Structure.from_dxf``, ``from_ifc``): their
single exemption to the layer rule names the package, not each module (ADR-5).
"""

from archlux.io.dxf_io import load_dxf_plan, load_dxf_structure
from archlux.io.ifc_io import load_ifc_plan, load_ifc_structure
from archlux.io.json_io import load, write

__all__ = [
    "load",
    "load_dxf_plan",
    "load_dxf_structure",
    "load_ifc_plan",
    "load_ifc_structure",
    "write",
]
