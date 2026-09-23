"""Aller-retour JSON : le critère de fin du jalon 1.

La propriété centrale est l'identité ``depuis_dict(vers_dict(p)) == p``. Elle n'est pas
tautologique : l'égalité vient du `dataclass` gelé, pas d'une comparaison réécrite ici,
et elle casse dès qu'un champ est oublié dans la sérialisation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings

from archlux.erreurs import InvariantViole
from archlux.io.json_io import VERSION_SCHEMA, depuis_dict, vers_dict
from archlux.types import Certificat, Mur, Ouverture, Piece, Plan, PreuveGeometrique
from tests.proprietes.strategies import plans_quelconques

PLAN_T2 = Plan(
    pieces=(
        Piece(id="sejour", type="sejour", x=0.0, y=0.0, w=4.0, h=3.5),
        Piece(id="sdb", type="sdb", x=4.0, y=0.0, w=2.0, h=2.5),
    ),
    murs=(Mur(id="m_sud", a=(0.0, 0.0), b=(6.0, 0.0), porteur=True),),
    ouvertures=(Ouverture(id="f1", mur_id="m_sud", s=0.3, largeur_rel=0.25),),
    contour=((0.0, 0.0), (6.0, 0.0), (6.0, 3.5), (0.0, 3.5)),
)


@given(plan=plans_quelconques())
@settings(max_examples=200, deadline=None)
def test_aller_retour_en_memoire(plan: Plan) -> None:
    """Aucune information n'est perdue entre le plan et sa forme JSON."""
    assert depuis_dict(vers_dict(plan)) == plan


def test_aller_retour_sur_disque(tmp_path: Path) -> None:
    """``Plan.to_json`` puis ``Plan.from_json`` rendent le plan d'origine."""
    chemin = tmp_path / "plan.json"
    PLAN_T2.to_json(chemin)
    assert Plan.from_json(chemin) == PLAN_T2


def test_le_certificat_survit_a_l_aller_retour() -> None:
    """Un plan légalisé porte son certificat ; le relire ne doit pas le perdre."""
    preuve = PreuveGeometrique(
        valide=True,
        chevauchement=False,
        jours=False,
        surfaces_ok=True,
        structure_preservee=True,
        deplacement_max=0.21,
        violations=(),
    )
    legalise = Plan(
        pieces=PLAN_T2.pieces,
        murs=PLAN_T2.murs,
        ouvertures=PLAN_T2.ouvertures,
        contour=PLAN_T2.contour,
        certificat=Certificat(geometrie=preuve),
    )
    relu = depuis_dict(vers_dict(legalise))
    assert relu.certificat is not None
    assert relu.certificat.geometrie.deplacement_max == pytest.approx(0.21)
    assert relu.certificat.performance is None


def test_la_version_du_schema_est_ecrite() -> None:
    """Un fichier sans version déclarée serait illisible dans deux ans."""
    assert vers_dict(PLAN_T2)["schema"] == VERSION_SCHEMA


def test_une_version_inconnue_est_refusee() -> None:
    """Mieux vaut refuser bruyamment que deviner le format."""
    donnees = vers_dict(PLAN_T2)
    donnees["schema"] = "999"
    with pytest.raises(InvariantViole):
        depuis_dict(donnees)


def test_l_ecriture_est_reproductible(tmp_path: Path) -> None:
    """Deux écritures du même plan donnent les mêmes octets.

    Sans cela, l'empreinte d'un manifeste change d'une exécution à l'autre et la
    reproductibilité annoncée par le README n'est pas tenue.
    """
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    PLAN_T2.to_json(a)
    PLAN_T2.to_json(b)
    assert a.read_bytes() == b.read_bytes()
