"""IFC4 export: minimal SPF (CI); IfcOpenShell if extra ``bim``."""

from __future__ import annotations

import hashlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux._version import __version__
from archlux.errors import ArchluxError
from archlux.export.pathologie import diagnose
from archlux.types import Plan

__all__ = ["ExportReport", "to_ifc"]


@dataclass(frozen=True, slots=True)
class ExportReport:
    """Result of an IFC export."""

    valid: bool
    path: Path
    pathologies: tuple[str, ...]
    engine: str
    """Writer **actually** used: ``"spf-minimal"`` or ``"refuse"``.

    Never name a library that did not write the file: this field ends up in
    reproducibility traces, where a false provenance is worse than none.
    """

    n_spaces: int
    ifcopenshell_available: bool = False
    """``ifcopenshell`` is installed (extra ``bim``). **Available != used**: the
    minimal SPF remains the sole writer as long as no code path calls it."""


@renamed_parameters({"chemin": "path"})
def to_ifc(plan: Plan, path: Path | str, *, validate: bool = True) -> ExportReport:
    """Export a plan to IFC4 (spaces = rooms; walls; annotated openings).

    Parameters
    ----------
    plan : Plan
        Plan to export. Any certificate is appended as ``Pset_Archlux``.
    path : Path or str
        ``.ifc`` file (overwritten).
    validate : bool, optional
        If true (default), a pathological plan is **not** written.

    Returns
    -------
    ExportReport
        ``valid`` follows the pathology diagnostic. ``engine`` names the writer
        actually used — always ``"spf-minimal"`` today. The presence of
        ``ifcopenshell`` is reported separately (``ifcopenshell_available``): the
        previous version appended ``"+ifcopenshell"`` on the sole basis of
        ``find_spec``, even though no line of the file came from it.
    """
    path = Path(path)
    diag = diagnose(plan)
    if validate and not diag.exportable:
        return ExportReport(
            valid=False,
            path=path,
            pathologies=diag.pathologies,
            engine="refuse",
            n_spaces=0,
        )

    engine = _ecrire_spf_minimal(plan, path)

    return ExportReport(
        valid=diag.exportable,
        path=path,
        pathologies=diag.pathologies,
        engine=engine,
        n_spaces=len(plan.rooms),
        ifcopenshell_available=importlib.util.find_spec("ifcopenshell") is not None,
    )


def _annexe_certificat(plan: Plan) -> str:
    """Text annex; a rendering failure must not block the leaf export."""
    if plan.certificate is None:
        return ""
    try:
        texte = plan.certificate.report()
    except (ImportError, AttributeError, ArchluxError):
        # ``report()`` imports ``certify`` locally: outside the ``export`` graph.
        texte = "certificate present"
    return _safe(texte.replace("\n", " | "), lim=1800)


def _safe(texte: str, *, lim: int = 120) -> str:
    """Neutralize apostrophes and backslashes, and truncate, for a STEP string."""
    return texte.replace("'", " ").replace("\\", "/")[:lim]


_IFC_BASE64 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"
"""Alphabet of ``IfcGloballyUniqueId`` (IFC base 64, not RFC 4648)."""


def _guid(etiquette: str) -> str:
    """Deterministic IFC identifier derived from a stable label.

    The parameter is **not** a seed in the sense of `ARCHITECTURE.md` §7: nothing
    is sampled here.

    The 128 first bits of SHA-256 of the label, written in IFC base 64: 22 characters
    of ``0-9A-Za-z_$``, the first one in ``0-3`` (22 x 6 = 132 bits, the top 4 are
    zero). ``ifcopenshell.guid.expand`` decodes it. The previous version wrote 22
    hexadecimal characters, rejected by every IFC validator (PLAN.md phase 2, J6).
    """
    nombre = int.from_bytes(hashlib.sha256(etiquette.encode()).digest()[:16], "big")
    chiffres = []
    for _ in range(22):
        nombre, reste = divmod(nombre, 64)
        chiffres.append(_IFC_BASE64[reste])
    return "".join(reversed(chiffres))


def _version_paquet() -> str:
    """Version of the source code (avoids a stale install metadata)."""
    return __version__


def _ecrire_spf_minimal(plan: Plan, path: Path) -> str:
    """Deterministic IFC4 SPF: Project / Site / Building / Storey / Space / Wall."""
    # GlobalIds must be unique across files, not only within one: salted by the plan
    # geometry, two different plans never share one, and one plan always gets the same.
    # Values only, never ``repr`` of the dataclasses: a class or field rename must not
    # change the GlobalIds of the same plan (BIM tools track objects by them).
    geometry = (
        [(r.id, r.type, r.x, r.y, r.w, r.h) for r in plan.rooms],
        [(w.id, w.a, w.b, w.load_bearing, w.thickness) for w in plan.walls],
        [
            (o.id, o.wall_id, o.s, o.relative_width, o.sill_height, o.head_height)
            for o in plan.openings
        ],
        list(plan.outline),
    )
    salt = hashlib.sha256(repr(geometry).encode()).hexdigest()[:16]

    def guid(label: str) -> str:
        """``IfcGloballyUniqueId`` of ``label`` in this plan."""
        return _guid(f"{salt}/{label}")

    ents: list[str] = []
    nxt = 1

    def alloc() -> int:
        """Reserve the next STEP entity number."""
        nonlocal nxt
        cur = nxt
        nxt += 1
        return cur

    def emit(num: int, corps: str) -> None:
        """Write a STEP entity line to the buffer."""
        ents.append(f"#{num}={corps};")

    def point(x: float, y: float, z: float = 0.0) -> int:
        """Emit an ``IFCCARTESIANPOINT`` and return its number."""
        num = alloc()
        emit(num, f"IFCCARTESIANPOINT(({x:.6f},{y:.6f},{z:.6f}))")
        return num

    def point2(x: float, y: float) -> int:
        """Emit a 2D ``IFCCARTESIANPOINT``: the vertices of a ``Curve2D`` representation."""
        num = alloc()
        emit(num, f"IFCCARTESIANPOINT(({x:.6f},{y:.6f}))")
        return num

    def axis2(x: float, y: float, z: float = 0.0) -> int:
        """Emit an ``IFCAXIS2PLACEMENT3D`` at the given position."""
        p = point(x, y, z)
        num = alloc()
        emit(num, f"IFCAXIS2PLACEMENT3D(#{p},$,$)")
        return num

    id_pers = alloc()
    emit(id_pers, "IFCPERSON($,$,'archlux',$,$,$,$,$)")
    id_org = alloc()
    emit(id_org, "IFCORGANIZATION($,'archlux',$,$,$)")
    # ``ApplicationDeveloper`` is mandatory in the IFC4 schema: leaving it as ``$``
    # produced a file that a strict validator rejects.
    id_app = alloc()
    emit(id_app, f"IFCAPPLICATION(#{id_org},'{_version_paquet()}','archlux','archlux')")
    id_po = alloc()
    emit(id_po, f"IFCPERSONANDORGANIZATION(#{id_pers},#{id_org},$)")
    id_owner = alloc()
    # No ChangeAction: without LastModifiedDate, IFC4 rule CorrectChangeAction forbids
    # .ADDED. (ifcopenshell.validate, PLAN.md phase 2, J6).
    emit(id_owner, f"IFCOWNERHISTORY(#{id_po},#{id_app},$,$,$,$,$,0)")
    id_unit = alloc()
    emit(id_unit, "IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.)")
    id_units = alloc()
    emit(id_units, f"IFCUNITASSIGNMENT((#{id_unit}))")

    id_world = axis2(0.0, 0.0, 0.0)
    id_ctx = alloc()
    emit(
        id_ctx,
        f"IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.0E-5,#{id_world},$)",
    )
    id_proj = alloc()
    emit(
        id_proj,
        f"IFCPROJECT('{guid('project')}',#{id_owner},'archlux',$,$,$,$,(#{id_ctx}),#{id_units})",
    )

    id_site_ax = axis2(0.0, 0.0, 0.0)
    id_site_pl = alloc()
    emit(id_site_pl, f"IFCLOCALPLACEMENT($,#{id_site_ax})")
    id_site = alloc()
    emit(
        id_site,
        f"IFCSITE('{guid('site')}',#{id_owner},'site',$,$,#{id_site_pl},$,$,.ELEMENT.,$,$,$,$,$)",
    )

    id_bat_ax = axis2(0.0, 0.0, 0.0)
    id_bat_pl = alloc()
    emit(id_bat_pl, f"IFCLOCALPLACEMENT(#{id_site_pl},#{id_bat_ax})")
    id_bat = alloc()
    emit(
        id_bat,
        f"IFCBUILDING('{guid('building')}',#{id_owner},'batiment',$,$,#{id_bat_pl},$,$,.ELEMENT.,$,$,$)",
    )

    id_floor_ax = axis2(0.0, 0.0, 0.0)
    id_floor_pl = alloc()
    emit(id_floor_pl, f"IFCLOCALPLACEMENT(#{id_bat_pl},#{id_floor_ax})")
    id_etage = alloc()
    emit(
        id_etage,
        f"IFCBUILDINGSTOREY('{guid('storey')}',#{id_owner},'RDC',$,$,#{id_floor_pl},$,$,.ELEMENT.,0.0)",
    )

    for rel_id, parent, enfants in (
        (alloc(), id_proj, (id_site,)),
        (alloc(), id_site, (id_bat,)),
        (alloc(), id_bat, (id_etage,)),
    ):
        refs = ",".join(f"#{e}" for e in enfants)
        emit(
            rel_id,
            f"IFCRELAGGREGATES('{guid(f'agg{rel_id}')}',#{id_owner},$,$,#{parent},({refs}))",
        )

    espaces: list[int] = []
    for piece in plan.rooms:
        coins = (
            (piece.x, piece.y),
            (piece.x + piece.w, piece.y),
            (piece.x + piece.w, piece.y + piece.h),
            (piece.x, piece.y + piece.h),
            (piece.x, piece.y),
        )
        pts = [point2(x, y) for x, y in coins]
        id_poly = alloc()
        emit(id_poly, f"IFCPOLYLINE(({','.join(f'#{p}' for p in pts)}))")
        id_ax = axis2(0.0, 0.0, 0.0)
        id_pl = alloc()
        emit(id_pl, f"IFCLOCALPLACEMENT(#{id_floor_pl},#{id_ax})")
        id_sr = alloc()
        emit(id_sr, f"IFCSHAPEREPRESENTATION(#{id_ctx},'FootPrint','Curve2D',(#{id_poly}))")
        id_psd = alloc()
        emit(id_psd, f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{id_sr}))")
        id_space = alloc()
        emit(
            id_space,
            f"IFCSPACE('{guid(f'space/{piece.id}')}',#{id_owner},'{_safe(piece.id)}',"
            f"$,'{_safe(piece.type)}',#{id_pl},#{id_psd},$,.ELEMENT.,.INTERNAL.,$)",
        )
        espaces.append(id_space)

    if espaces:
        # ``IfcSpace`` is an ``IfcSpatialStructureElement``: it **aggregates** to the
        # storey. ``IfcRelContainedInSpatialStructure`` explicitly forbids spatial
        # structure elements in ``RelatedElements`` (IFC4), and that is what the
        # previous version wrote — a file rejected by every validator.
        id_agg = alloc()
        emit(
            id_agg,
            f"IFCRELAGGREGATES('{guid('agg_espaces')}',#{id_owner},$,$,#{id_etage},"
            f"({','.join(f'#{e}' for e in espaces)}))",
        )

    murs_ids: list[int] = []
    wall_entity: dict[str, int] = {}
    for mur in plan.walls:
        # Placed at the storey origin: the axis already holds absolute coordinates. The
        # previous placement at ``mur.a`` shifted every wall by ``a`` (drawn from 2a).
        id_ax = axis2(0.0, 0.0, 0.0)
        id_pl = alloc()
        emit(id_pl, f"IFCLOCALPLACEMENT(#{id_floor_pl},#{id_ax})")
        id_p1 = point2(mur.a[0], mur.a[1])
        id_p2 = point2(mur.b[0], mur.b[1])
        id_line = alloc()
        emit(id_line, f"IFCPOLYLINE((#{id_p1},#{id_p2}))")
        id_sr = alloc()
        emit(id_sr, f"IFCSHAPEREPRESENTATION(#{id_ctx},'Axis','Curve2D',(#{id_line}))")
        id_psd = alloc()
        emit(id_psd, f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{id_sr}))")
        id_wall = alloc()
        emit(
            id_wall,
            f"IFCWALL('{guid(f'wall/{mur.id}')}',#{id_owner},'{_safe(mur.id)}',$,$,#{id_pl},#{id_psd},$,$)",
        )
        murs_ids.append(id_wall)
        wall_entity[mur.id] = id_wall

    if murs_ids:
        # Walls, on the other hand, are indeed elements **contained** in the storey.
        # Without this relation they remained orphaned from any spatial structure.
        id_cont = alloc()
        emit(
            id_cont,
            f"IFCRELCONTAINEDINSPATIALSTRUCTURE('{guid('contain')}',#{id_owner},$,$,"
            f"({','.join(f'#{e}' for e in murs_ids)}),#{id_etage})",
        )

    for ouv in plan.openings:
        id_ouv = alloc()
        emit(
            id_ouv,
            f"IFCOPENINGELEMENT('{guid(f'opening/{ouv.id}')}',#{id_owner},'{_safe(ouv.id)}',"
            f"$,'mur={_safe(ouv.wall_id)} s={ouv.s:.4f}',$,$,$,$)",
        )
        if ouv.wall_id in wall_entity:  # else refused by diagnostiquer when validating
            id_void = alloc()
            emit(
                id_void,
                f"IFCRELVOIDSELEMENT('{guid(f'void/{ouv.id}')}',#{id_owner},$,$,"
                f"#{wall_entity[ouv.wall_id]},#{id_ouv})",
            )

    annexe = _annexe_certificat(plan)
    if annexe:
        id_prop = alloc()
        emit(
            id_prop,
            f"IFCPROPERTYSINGLEVALUE('CertificatArchlux',$,IFCTEXT('{annexe}'),$)",
        )
        id_pset = alloc()
        emit(
            id_pset,
            f"IFCPROPERTYSET('{guid('pset')}',#{id_owner},'Pset_Archlux',$,(#{id_prop}))",
        )
        id_rel = alloc()
        emit(
            id_rel,
            f"IFCRELDEFINESBYPROPERTIES('{guid('relp')}',#{id_owner},$,$,(#{id_bat}),#{id_pset})",
        )

    texte = "\n".join(
        [
            "ISO-10303-21;",
            "HEADER;",
            "FILE_DESCRIPTION(('ViewDefinition [DesignTransferView_V1.0]'),'2;1');",
            "FILE_NAME('archlux.ifc','',('archlux'),('archlux'),'archlux','archlux','');",
            "FILE_SCHEMA(('IFC4'));",
            "ENDSEC;",
            "DATA;",
            *ents,
            "ENDSEC;",
            "END-ISO-10303-21;",
        ]
    )
    path.write_text(texte + "\n", encoding="utf-8")
    return "spf-minimal"


__getattr__ = lazy_aliases(
    __name__,
    {
        "RapportExport": Alias(ExportReport, "archlux.export.ifc.ExportReport"),
    },
)
