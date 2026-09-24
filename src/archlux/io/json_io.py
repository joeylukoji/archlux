"""Aller-retour JSON des plans. Schéma versionné, sérialisation déterministe.

Le schéma porte un numéro de version : un plan écrit par ``0.1.x`` doit rester lisible
par ``0.2.x``. Les clés sont triées à l'écriture, sinon deux exécutions identiques
produisent deux empreintes différentes et la reproductibilité annoncée n'est pas tenue.

La conversion est écrite **à la main**, champ par champ, plutôt que dérivée par
introspection des `dataclass`. C'est plus long et c'est voulu : ajouter un champ au
modèle doit obliger à décider ce qu'il devient dans le format publié, au lieu
d'apparaître silencieusement dans des fichiers que d'autres outils lisent déjà.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from archlux.erreurs import InvariantViole
from archlux.types import (
    REGIMES,
    BornePerformance,
    Certificat,
    Manifeste,
    ModeleTrace,
    Mur,
    Ouverture,
    Piece,
    Plan,
    Point,
    PreuveGeometrique,
    Regime,
)

__all__ = [
    "VERSION_SCHEMA",
    "charger",
    "depuis_dict",
    "ecrire",
    "manifeste_vers_dict",
    "vers_dict",
]

VERSION_SCHEMA = "1"
"""Version du schéma JSON. Incrémentée à tout changement non rétrocompatible."""


# ======================================================================================
# Conversions élémentaires
# ======================================================================================


def _reel(valeur: Any, ou: str) -> float:
    """Lire un flottant **fini**.

    ``json.loads`` accepte les littéraux ``NaN`` et ``Infinity``. Sans cette garde, un
    fichier produit par un autre outil introduirait des valeurs non finies dans le
    solveur, où elles se propagent silencieusement jusqu'à un certificat absurde.
    ``ecrire`` refusant déjà de les écrire, la lecture doit refuser de les lire.
    """
    reel = float(valeur)
    if not math.isfinite(reel):
        raise InvariantViole((f"{ou} : valeur non finie ({valeur!r})",))
    return reel


def _point(valeur: Any, ou: str = "point") -> Point:
    """Lire un point ``[x, y]``, en refusant tout ce qui n'en est pas un."""
    if not isinstance(valeur, (list, tuple)) or len(valeur) != 2:
        raise InvariantViole((f"point attendu sous la forme [x, y], reçu {valeur!r}",))
    return (_reel(valeur[0], f"{ou}.x"), _reel(valeur[1], f"{ou}.y"))


def _paires(valeur: Any) -> tuple[tuple[str, str], ...]:
    """Normaliser une liste JSON de paires en tuple de couples de chaines."""
    return tuple((str(cle), str(val)) for cle, val in valeur)


def _verifier_plages(plan: Plan) -> None:
    """Vérifier les plages documentées par `ARCHITECTURE.md` §6.

    **La validation a lieu ici et pas dans les constructeurs** (ADR-6). La frontière JSON
    est l'endroit où les données viennent de l'extérieur ; c'est donc là qu'il faut les
    refuser. Valider dans ``__post_init__`` interdirait au solveur de traverser un état
    intermédiaire hors plage, et ferait payer une vérification à chaque construction dans
    une boucle de Frank-Wolfe qui en fait des milliers.

    Toutes les violations sont rapportées ensemble : corriger un fichier une erreur à la
    fois est un supplice, et rien n'oblige à ne rendre que la première.

    Raises
    ------
    InvariantViole
        Au moins une valeur est hors de sa plage. ``violations`` les liste toutes.

    Complexity
    ----------
    O(n) sur le nombre d'éléments du plan.
    """
    violations: list[str] = []
    for piece in plan.pieces:
        for champ, valeur in (("w", piece.w), ("h", piece.h)):
            if valeur <= 0.0:
                violations.append(f"piece {piece.id} : {champ} = {valeur} ; attendu > 0")
    for mur in plan.murs:
        if mur.epaisseur <= 0.0:
            violations.append(f"mur {mur.id} : epaisseur = {mur.epaisseur} ; attendu > 0")
    for ouverture in plan.ouvertures:
        if not 0.0 <= ouverture.s <= 1.0:
            violations.append(f"ouverture {ouverture.id} : s = {ouverture.s} ; attendu dans [0, 1]")
        if not 0.0 < ouverture.largeur_rel <= 1.0:
            violations.append(
                f"ouverture {ouverture.id} : largeur_rel = {ouverture.largeur_rel} ;"
                " attendu dans ]0, 1]"
            )
    if violations:
        raise InvariantViole(tuple(violations))


# ======================================================================================
# Certificat
# ======================================================================================


def _preuve_vers_dict(preuve: PreuveGeometrique) -> dict[str, Any]:
    """Serialiser une preuve geometrique ; aucun champ de probabilite n'y entre."""
    return {
        "valide": preuve.valide,
        "chevauchement": preuve.chevauchement,
        "jours": preuve.jours,
        "surfaces_ok": preuve.surfaces_ok,
        "structure_preservee": preuve.structure_preservee,
        "deplacement_max": preuve.deplacement_max,
        "violations": list(preuve.violations),
    }


def _preuve_depuis_dict(donnees: Any) -> PreuveGeometrique:
    """Reconstruire une preuve geometrique depuis sa forme JSON."""
    return PreuveGeometrique(
        valide=bool(donnees["valide"]),
        chevauchement=bool(donnees["chevauchement"]),
        jours=bool(donnees["jours"]),
        surfaces_ok=bool(donnees["surfaces_ok"]),
        structure_preservee=bool(donnees["structure_preservee"]),
        deplacement_max=_reel(donnees["deplacement_max"], "preuve.deplacement_max"),
        violations=tuple(str(v) for v in donnees["violations"]),
    )


def _borne_vers_dict(borne: BornePerformance) -> dict[str, Any]:
    """Serialiser une borne de performance, couverture et n_calibration compris."""
    return {
        "indicateur": borne.indicateur,
        "valeur": borne.valeur,
        "borne_inf": borne.borne_inf,
        "borne_sup": borne.borne_sup,
        "couverture": borne.couverture,
        "n_calibration": borne.n_calibration,
        "regime": borne.regime,
    }


def _regime(donnees: Any) -> Regime:
    """The regime of a serialized bound; missing or unknown is refused."""
    regime = donnees.get("regime") if isinstance(donnees, dict) else None
    if regime not in REGIMES:
        raise InvariantViole((f"borne.regime: expected one of {REGIMES}, got {regime!r}",))
    return regime  # type: ignore[no-any-return]


def _borne_depuis_dict(donnees: Any) -> BornePerformance:
    """Reconstruire une borne de performance ; refuser un indicateur inconnu."""
    indicateur = donnees["indicateur"]
    if indicateur not in ("sDA", "ASE", "UDI", "vue"):
        raise InvariantViole((f"indicateur inconnu : {indicateur!r}",))
    return BornePerformance(
        indicateur=indicateur,
        valeur=_reel(donnees["valeur"], "borne.valeur"),
        borne_inf=_reel(donnees["borne_inf"], "borne.borne_inf"),
        borne_sup=_reel(donnees["borne_sup"], "borne.borne_sup"),
        couverture=_reel(donnees["couverture"], "borne.couverture"),
        n_calibration=int(donnees["n_calibration"]),
        # Files written before batch 1.6 carry no regime. They could only come from a
        # hand-built bound (legalize never filled one), so none is assumed: reading
        # such a bound as "exchangeable" would upgrade an unknown guarantee.
        regime=_regime(donnees),
    )


def manifeste_vers_dict(manifeste: Manifeste) -> dict[str, Any]:
    """Sérialiser un :class:`~archlux.types.Manifeste` (forme unique JSON / banc)."""
    modele = manifeste.modele
    return {
        "version": manifeste.version,
        "horodatage": manifeste.horodatage,
        "graine": manifeste.graine,
        "empreinte_donnees": manifeste.empreinte_donnees,
        "decoupage": manifeste.decoupage,
        "environnement": [list(p) for p in manifeste.environnement],
        "parametres": [list(p) for p in manifeste.parametres],
        "modele": None
        if modele is None
        else {
            "poids": modele.poids,
            "calibration_n": modele.calibration_n,
            "alpha": modele.alpha,
        },
    }


def _manifeste_depuis_dict(donnees: Any) -> Manifeste:
    """Reconstruire un manifeste, ``ModeleTrace`` compris s'il est present."""
    brut = donnees.get("modele")
    modele = None
    if brut is not None:
        modele = ModeleTrace(
            poids=str(brut["poids"]),
            calibration_n=int(brut["calibration_n"]),
            alpha=float(brut["alpha"]),
        )
    return Manifeste(
        version=str(donnees["version"]),
        horodatage=str(donnees["horodatage"]),
        graine=int(donnees["graine"]),
        empreinte_donnees=donnees["empreinte_donnees"],
        decoupage=donnees["decoupage"],
        environnement=_paires(donnees["environnement"]),
        parametres=_paires(donnees["parametres"]),
        modele=modele,
    )


def _certificat_vers_dict(certificat: Certificat | None) -> dict[str, Any] | None:
    """Serialiser un certificat ; ``None`` en performance reste explicite."""
    if certificat is None:
        return None
    performance = certificat.performance
    manifeste = certificat.manifeste
    return {
        "geometrie": _preuve_vers_dict(certificat.geometrie),
        # `None` explicite plutôt qu'une clé absente : « aucune garantie de performance »
        # est une information, pas un oubli de sérialisation.
        "performance": None if performance is None else _borne_vers_dict(performance),
        "duaux": [[libelle, cout] for libelle, cout in certificat.duaux],
        "manifeste": None if manifeste is None else manifeste_vers_dict(manifeste),
    }


def _certificat_depuis_dict(donnees: Any) -> Certificat | None:
    """Reconstruire un certificat, ou ``None`` si le plan n'en porte pas."""
    if donnees is None:
        return None
    performance = donnees["performance"]
    manifeste = donnees["manifeste"]
    return Certificat(
        geometrie=_preuve_depuis_dict(donnees["geometrie"]),
        performance=None if performance is None else _borne_depuis_dict(performance),
        duaux=tuple(
            (str(libelle), _reel(cout, f"dual {libelle}")) for libelle, cout in donnees["duaux"]
        ),
        manifeste=None if manifeste is None else _manifeste_depuis_dict(manifeste),
    )


# ======================================================================================
# Plan
# ======================================================================================


def vers_dict(plan: Plan) -> dict[str, Any]:
    """Projeter un plan en structure JSON-compatible, ordre stable.

    Parameters
    ----------
    plan : Plan
        Plan à encoder, proposé ou légalisé.

    Returns
    -------
    dict
        Structure portant ``schema``, la géométrie et le certificat éventuel.

    Guarantees
    ----------
    - Aucune : cette fonction ne fait que transcrire. Les garanties d'un plan sont
      portées par son ``certificat``, transcrit tel quel.

    Complexity
    ----------
    O(n) sur le nombre d'éléments du plan.
    """
    return {
        "schema": VERSION_SCHEMA,
        "contour": [[x, y] for x, y in plan.contour],
        "pieces": [
            {
                "id": p.id,
                "type": p.type,
                "x": p.x,
                "y": p.y,
                "w": p.w,
                "h": p.h,
            }
            for p in plan.pieces
        ],
        "murs": [
            {
                "id": m.id,
                "a": [m.a[0], m.a[1]],
                "b": [m.b[0], m.b[1]],
                "porteur": m.porteur,
                "epaisseur": m.epaisseur,
            }
            for m in plan.murs
        ],
        "ouvertures": [
            {
                "id": o.id,
                "mur_id": o.mur_id,
                "s": o.s,
                "largeur_rel": o.largeur_rel,
                "hauteur_allege": o.hauteur_allege,
                "hauteur_linteau": o.hauteur_linteau,
            }
            for o in plan.ouvertures
        ],
        "certificat": _certificat_vers_dict(plan.certificat),
    }


def depuis_dict(donnees: dict[str, Any]) -> Plan:
    """Reconstruire un plan depuis une structure JSON-compatible.

    Parameters
    ----------
    donnees : dict
        Structure telle que rendue par :func:`vers_dict`.

    Returns
    -------
    Plan
        Plan reconstruit, certificat compris s'il est présent.

    Raises
    ------
    InvariantViole
        Version de schéma absente ou inconnue, ou champ mal formé. Le format est refusé
        bruyamment plutôt que deviné : un plan mal relu produirait un certificat faux.

    Complexity
    ----------
    O(n) sur le nombre d'éléments du plan.
    """
    version = donnees.get("schema")
    if version != VERSION_SCHEMA:
        raise InvariantViole((f"schéma JSON {version!r} inconnu, attendu {VERSION_SCHEMA!r}",))
    try:
        plan = Plan(
            pieces=tuple(
                Piece(
                    id=str(p["id"]),
                    type=str(p["type"]),
                    x=_reel(p["x"], f"piece {p['id']}.x"),
                    y=_reel(p["y"], f"piece {p['id']}.y"),
                    w=_reel(p["w"], f"piece {p['id']}.w"),
                    h=_reel(p["h"], f"piece {p['id']}.h"),
                )
                for p in donnees["pieces"]
            ),
            murs=tuple(
                Mur(
                    id=str(m["id"]),
                    a=_point(m["a"], f"mur {m['id']}.a"),
                    b=_point(m["b"], f"mur {m['id']}.b"),
                    porteur=bool(m["porteur"]),
                    epaisseur=_reel(m["epaisseur"], f"mur {m['id']}.epaisseur"),
                )
                for m in donnees["murs"]
            ),
            ouvertures=tuple(
                Ouverture(
                    id=str(o["id"]),
                    mur_id=str(o["mur_id"]),
                    s=_reel(o["s"], f"ouverture {o['id']}.s"),
                    largeur_rel=_reel(o["largeur_rel"], f"ouverture {o['id']}.largeur_rel"),
                    hauteur_allege=_reel(
                        o["hauteur_allege"], f"ouverture {o['id']}.hauteur_allege"
                    ),
                    hauteur_linteau=_reel(
                        o["hauteur_linteau"], f"ouverture {o['id']}.hauteur_linteau"
                    ),
                )
                for o in donnees["ouvertures"]
            ),
            contour=tuple(_point(pt, f"contour[{i}]") for i, pt in enumerate(donnees["contour"])),
            certificat=_certificat_depuis_dict(donnees["certificat"]),
        )
    except (KeyError, TypeError, ValueError) as cause:
        raise InvariantViole((f"structure JSON invalide : {cause}",)) from cause
    _verifier_plages(plan)
    return plan


def charger(chemin: Path | str) -> Plan:
    """Lire un plan depuis un fichier JSON.

    Parameters
    ----------
    chemin : Path or str
        Fichier source, encodé en UTF-8.

    Returns
    -------
    Plan
        Plan reconstruit, certificat compris s'il est présent.

    Raises
    ------
    InvariantViole
        Le fichier n'est pas de l'UTF-8, n'est pas du JSON, ou ne respecte pas le
        schéma déclaré. Un fichier écrit en ISO-8859-1 par un autre outil remontait
        auparavant en ``UnicodeDecodeError`` nu, hors du domaine d'erreurs du projet
        (`ARCHITECTURE.md` §7).
    """
    try:
        texte = Path(chemin).read_text(encoding="utf-8")
    except UnicodeDecodeError as cause:
        raise InvariantViole((f"{chemin} n'est pas encodé en UTF-8 : {cause}",)) from cause
    try:
        donnees = json.loads(texte)
    except json.JSONDecodeError as cause:
        raise InvariantViole((f"{chemin} n'est pas du JSON valide : {cause}",)) from cause
    if not isinstance(donnees, dict):
        raise InvariantViole((f"{chemin} ne contient pas un objet JSON",))
    return depuis_dict(donnees)


def ecrire(plan: Plan, chemin: Path | str) -> None:
    r"""Écrire un plan en JSON, clés triées, encodage UTF-8, fin de ligne ``\n``.

    Le tri des clés et la fin de ligne fixée ne sont pas cosmétiques : sans eux, deux
    écritures du même plan donnent des octets différents, et l'empreinte inscrite dans un
    manifeste cesse d'identifier quoi que ce soit.

    Parameters
    ----------
    plan : Plan
        Plan à écrire.
    chemin : Path or str
        Fichier de destination ; son répertoire parent doit exister.

    Raises
    ------
    InvariantViole
        Le plan contient une valeur non finie (``NaN`` ou infini). C'est typiquement ce
        que produit un solveur bogué ; ``allow_nan=False`` refuse de l'écrire, et
        l'erreur est retypée pour rester dans le domaine d'erreurs du projet
        (`ARCHITECTURE.md` §7) plutôt que de remonter en ``ValueError`` de la
        bibliothèque standard.
    """
    try:
        texte = json.dumps(
            vers_dict(plan),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    except ValueError as cause:
        raise InvariantViole((f"valeur non finie dans le plan : {cause}",)) from cause
    Path(chemin).write_text(texte + "\n", encoding="utf-8", newline="\n")
