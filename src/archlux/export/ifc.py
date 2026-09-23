"""Export IFC4 : SPF minimal (CI) ; IfcOpenShell si extra ``bim``."""

from __future__ import annotations

import hashlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path

from archlux import __version__
from archlux.erreurs import ArchluxError
from archlux.export.pathologie import diagnostiquer
from archlux.types import Plan

__all__ = ["RapportExport", "to_ifc"]


@dataclass(frozen=True, slots=True)
class RapportExport:
    """Résultat d'un export IFC."""

    valide: bool
    chemin: Path
    pathologies: tuple[str, ...]
    moteur: str
    """Écrivain **réellement** employé : ``"spf-minimal"`` ou ``"refuse"``.

    Ne nomme jamais une bibliothèque qui n'a pas écrit le fichier : ce champ finit
    dans des traces de reproductibilité, où une provenance fausse est pire qu'absente.
    """

    n_espaces: int
    ifcopenshell_disponible: bool = False
    """``ifcopenshell`` est installé (extra ``bim``). **Disponible ≠ utilisé** : le
    SPF minimal reste l'unique écrivain tant qu'aucun chemin ne l'appelle."""


def to_ifc(plan: Plan, chemin: Path, *, validate: bool = True) -> RapportExport:
    """Exporter un plan en IFC4 (espaces = pièces ; murs ; baies annotées).

    Parameters
    ----------
    plan : Plan
        Plan à exporter. Le certificat éventuel est annexé en ``Pset_Archlux``.
    chemin : Path
        Fichier ``.ifc`` (écrasé).
    validate : bool, optional
        Si vrai (défaut), un plan pathologique n'est **pas** écrit.

    Returns
    -------
    RapportExport
        ``valide`` suit le diagnostic de pathologie. ``moteur`` nomme l'écrivain
        réellement employé — toujours ``"spf-minimal"`` aujourd'hui. La présence de
        ``ifcopenshell`` est rapportée à part (``ifcopenshell_disponible``) : la
        version précédente concaténait ``"+ifcopenshell"`` au seul vu de
        ``find_spec``, alors qu'aucune ligne du fichier n'en venait.
    """
    chemin = Path(chemin)
    diag = diagnostiquer(plan)
    if validate and not diag.exportable:
        return RapportExport(
            valide=False,
            chemin=chemin,
            pathologies=diag.pathologies,
            moteur="refuse",
            n_espaces=0,
        )

    moteur = _ecrire_spf_minimal(plan, chemin)

    return RapportExport(
        valide=diag.exportable,
        chemin=chemin,
        pathologies=diag.pathologies,
        moteur=moteur,
        n_espaces=len(plan.pieces),
        ifcopenshell_disponible=importlib.util.find_spec("ifcopenshell") is not None,
    )


def _annexe_certificat(plan: Plan) -> str:
    """Annexe texte ; l'échec de rendu ne doit pas bloquer l'export feuille."""
    if plan.certificat is None:
        return ""
    try:
        texte = plan.certificat.rapport()
    except (ImportError, AttributeError, ArchluxError):
        # ``rapport()`` importe ``certify`` en local : hors graphe d'``export``.
        texte = "certificat present"
    return _safe(texte.replace("\n", " | "), lim=1800)


def _safe(texte: str, *, lim: int = 120) -> str:
    """Neutraliser apostrophes et antislashs, et tronquer, pour une chaine STEP."""
    return texte.replace("'", " ").replace("\\", "/")[:lim]


def _guid(etiquette: str) -> str:
    """Identifiant IFC déterministe dérivé d'une étiquette stable.

    Le paramètre n'est **pas** une graine au sens d'`ARCHITECTURE.md` §7 : rien
    n'est échantillonné ici, et le nom ``seed`` prêtait à confusion dans un dépôt
    où « graine » a une signification contraignante.

    Limite connue : ``IfcGloballyUniqueId`` fait bien 22 caractères, mais l'encodage
    IFC est en base 64 (``0-9A-Za-z_$``) avec un premier caractère dans ``0-3``.
    Ces 22 caractères hexadécimaux respectent la longueur, pas l'encodage : les
    outils qui *décodent* le GUID (``ifcopenshell.guid.expand``) ne le retrouveront
    pas. Suffisant pour la CI et les visionneuses ; à remplacer par un vrai encodage
    base 64 IFC avant tout échange BIM réel.
    """
    return hashlib.sha256(etiquette.encode()).hexdigest()[:22]


def _version_paquet() -> str:
    """Version du code source (évite une métadonnée d'install périmée)."""
    return __version__


def _ecrire_spf_minimal(plan: Plan, chemin: Path) -> str:
    """IFC4 SPF déterministe : Project / Site / Building / Storey / Space / Wall."""
    ents: list[str] = []
    nxt = 1

    def alloc() -> int:
        """Reserver le prochain numero d'entite STEP."""
        nonlocal nxt
        cur = nxt
        nxt += 1
        return cur

    def emit(num: int, corps: str) -> None:
        """Ecrire une ligne d'entite STEP dans le tampon."""
        ents.append(f"#{num}={corps};")

    def point(x: float, y: float, z: float = 0.0) -> int:
        """Emettre un ``IFCCARTESIANPOINT`` et rendre son numero."""
        num = alloc()
        emit(num, f"IFCCARTESIANPOINT(({x:.6f},{y:.6f},{z:.6f}))")
        return num

    def axis2(x: float, y: float, z: float = 0.0) -> int:
        """Emettre un ``IFCAXIS2PLACEMENT3D`` a la position donnee."""
        p = point(x, y, z)
        num = alloc()
        emit(num, f"IFCAXIS2PLACEMENT3D(#{p},$,$)")
        return num

    id_pers = alloc()
    emit(id_pers, "IFCPERSON($,$,'archlux',$,$,$,$,$)")
    id_org = alloc()
    emit(id_org, "IFCORGANIZATION($,'archlux',$,$,$)")
    # ``ApplicationDeveloper`` est obligatoire au schéma IFC4 : le laisser à ``$``
    # produisait un fichier qu'un validateur strict rejette.
    id_app = alloc()
    emit(id_app, f"IFCAPPLICATION(#{id_org},'{_version_paquet()}','archlux','archlux')")
    id_po = alloc()
    emit(id_po, f"IFCPERSONANDORGANIZATION(#{id_pers},#{id_org},$)")
    id_owner = alloc()
    emit(id_owner, f"IFCOWNERHISTORY(#{id_po},#{id_app},$,.ADDED.,$,$,$,0)")
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
        f"IFCPROJECT('{_guid('project')}',#{id_owner},'archlux',$,$,$,$,"
        f"(#{id_ctx}),#{id_units})",
    )

    id_site_ax = axis2(0.0, 0.0, 0.0)
    id_site_pl = alloc()
    emit(id_site_pl, f"IFCLOCALPLACEMENT($,#{id_site_ax})")
    id_site = alloc()
    emit(
        id_site,
        f"IFCSITE('{_guid('site')}',#{id_owner},'site',$,$,#{id_site_pl},$,$,.ELEMENT.,$,$,$,$,$)",
    )

    id_bat_ax = axis2(0.0, 0.0, 0.0)
    id_bat_pl = alloc()
    emit(id_bat_pl, f"IFCLOCALPLACEMENT(#{id_site_pl},#{id_bat_ax})")
    id_bat = alloc()
    emit(
        id_bat,
        f"IFCBUILDING('{_guid('building')}',#{id_owner},'batiment',$,$,#{id_bat_pl},$,$,.ELEMENT.,$,$,$)",
    )

    id_et_ax = axis2(0.0, 0.0, 0.0)
    id_et_pl = alloc()
    emit(id_et_pl, f"IFCLOCALPLACEMENT(#{id_bat_pl},#{id_et_ax})")
    id_etage = alloc()
    emit(
        id_etage,
        f"IFCBUILDINGSTOREY('{_guid('storey')}',#{id_owner},'RDC',$,$,#{id_et_pl},$,$,.ELEMENT.,0.0)",
    )

    for rel_id, parent, enfants in (
        (alloc(), id_proj, (id_site,)),
        (alloc(), id_site, (id_bat,)),
        (alloc(), id_bat, (id_etage,)),
    ):
        refs = ",".join(f"#{e}" for e in enfants)
        emit(
            rel_id,
            f"IFCRELAGGREGATES('{_guid(f'agg{rel_id}')}',#{id_owner},$,$,#{parent},({refs}))",
        )

    espaces: list[int] = []
    for piece in plan.pieces:
        coins = (
            (piece.x, piece.y),
            (piece.x + piece.w, piece.y),
            (piece.x + piece.w, piece.y + piece.h),
            (piece.x, piece.y + piece.h),
            (piece.x, piece.y),
        )
        pts = [point(x, y) for x, y in coins]
        id_poly = alloc()
        emit(id_poly, f"IFCPOLYLINE(({','.join(f'#{p}' for p in pts)}))")
        id_ax = axis2(0.0, 0.0, 0.0)
        id_pl = alloc()
        emit(id_pl, f"IFCLOCALPLACEMENT(#{id_et_pl},#{id_ax})")
        id_sr = alloc()
        emit(id_sr, f"IFCSHAPEREPRESENTATION(#{id_ctx},'FootPrint','Curve2D',(#{id_poly}))")
        id_psd = alloc()
        emit(id_psd, f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{id_sr}))")
        id_space = alloc()
        emit(
            id_space,
            f"IFCSPACE('{_guid(piece.id)}',#{id_owner},'{_safe(piece.id)}',"
            f"$,'{_safe(piece.type)}',#{id_pl},#{id_psd},$,.ELEMENT.,.INTERNAL.,$)",
        )
        espaces.append(id_space)

    if espaces:
        # ``IfcSpace`` est un ``IfcSpatialStructureElement`` : il s'**agrège** à
        # l'étage. ``IfcRelContainedInSpatialStructure`` interdit explicitement les
        # éléments de structure spatiale dans ``RelatedElements`` (IFC4), et c'est ce
        # qu'écrivait la version précédente — un fichier rejeté par tout validateur.
        id_agg = alloc()
        emit(
            id_agg,
            f"IFCRELAGGREGATES('{_guid('agg_espaces')}',#{id_owner},$,$,#{id_etage},"
            f"({','.join(f'#{e}' for e in espaces)}))",
        )

    murs_ids: list[int] = []
    for mur in plan.murs:
        id_ax = axis2(mur.a[0], mur.a[1], 0.0)
        id_pl = alloc()
        emit(id_pl, f"IFCLOCALPLACEMENT(#{id_et_pl},#{id_ax})")
        id_p1 = point(mur.a[0], mur.a[1])
        id_p2 = point(mur.b[0], mur.b[1])
        id_line = alloc()
        emit(id_line, f"IFCPOLYLINE((#{id_p1},#{id_p2}))")
        id_sr = alloc()
        emit(id_sr, f"IFCSHAPEREPRESENTATION(#{id_ctx},'Axis','Curve2D',(#{id_line}))")
        id_psd = alloc()
        emit(id_psd, f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{id_sr}))")
        id_wall = alloc()
        emit(
            id_wall,
            f"IFCWALL('{_guid(mur.id)}',#{id_owner},'{_safe(mur.id)}',$,$,#{id_pl},#{id_psd},$,$)",
        )
        murs_ids.append(id_wall)

    if murs_ids:
        # Les murs, eux, sont bien des éléments **contenus** dans l'étage. Sans cette
        # relation ils restaient orphelins de toute structure spatiale.
        id_cont = alloc()
        emit(
            id_cont,
            f"IFCRELCONTAINEDINSPATIALSTRUCTURE('{_guid('contain')}',#{id_owner},$,$,"
            f"({','.join(f'#{e}' for e in murs_ids)}),#{id_etage})",
        )

    for ouv in plan.ouvertures:
        id_ouv = alloc()
        emit(
            id_ouv,
            f"IFCOPENINGELEMENT('{_guid(ouv.id)}',#{id_owner},'{_safe(ouv.id)}',"
            f"$,'mur={_safe(ouv.mur_id)} s={ouv.s:.4f}',$,$,$,$)",
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
            f"IFCPROPERTYSET('{_guid('pset')}',#{id_owner},'Pset_Archlux',$,(#{id_prop}))",
        )
        id_rel = alloc()
        emit(
            id_rel,
            f"IFCRELDEFINESBYPROPERTIES('{_guid('relp')}',#{id_owner},$,$,(#{id_bat}),#{id_pset})",
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
    chemin.write_text(texte + "\n", encoding="utf-8")
    return "spf-minimal"
