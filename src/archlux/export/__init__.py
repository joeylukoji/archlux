"""CAD/BIM export: IFC, DXF, survival rate.

Leaf layer: ``types`` + ``errors``.
``ifcopenshell`` is optional (extra ``bim``): the core writes a minimal IFC4 SPF
sufficient for CI and rectangular plans.
"""

from archlux._deprecation import Alias, lazy_aliases
from archlux.export.dxf import to_dxf
from archlux.export.ifc import ExportReport, to_ifc
from archlux.export.pathologie import PathologyDiagnostic, diagnose
from archlux.export.survie import survival_rate
from archlux.export.svg import render as render_svg
from archlux.export.wilson import wilson_interval

__all__ = [
    "ExportReport",
    "PathologyDiagnostic",
    "diagnose",
    "render_svg",
    "survival_rate",
    "to_dxf",
    "to_ifc",
    "wilson_interval",
]

__getattr__ = lazy_aliases(
    __name__,
    {
        "DiagnosticPathologie": Alias(PathologyDiagnostic, "archlux.export.PathologyDiagnostic"),
        "RapportExport": Alias(ExportReport, "archlux.export.ExportReport"),
        "diagnostiquer": Alias(diagnose, "archlux.export.diagnose"),
        "intervalle_wilson": Alias(wilson_interval, "archlux.export.wilson_interval"),
    },
)
