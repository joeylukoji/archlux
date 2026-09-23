"""Export IFC / DXF et taux de survie — `MILESTONE-6.md` §4."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings

from archlux.erreurs import InvariantViole
from archlux.export import diagnostiquer, survival_rate, to_dxf, to_ifc
from archlux.export.wilson import intervalle_wilson
from archlux.types import Mur, Piece, Plan
from tests.proprietes.strategies import CONTEXTE_DEFAUT, plans_valides


def _plan_sain() -> Plan:
    return Plan(
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            Piece(id="b", type="chambre", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(Mur(id="m1", a=(0.0, 0.0), b=(12.0, 0.0), porteur=True),),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )


def _plan_pathologique() -> Plan:
    return Plan(
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=7.0, h=9.0),
            Piece(id="b", type="chambre", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(Mur(id="nul", a=(1.0, 1.0), b=(1.0, 1.0), porteur=False),),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )


@given(plan=plans_valides())
@settings(max_examples=40, deadline=None)
def test_export_valide(plan: Plan) -> None:
    """`MILESTONE-6.md` §4 : to_ifc sur plans_valides reste valide."""
    assert diagnostiquer(plan).exportable
    with TemporaryDirectory() as tmp:
        chemin = Path(tmp) / "plan.ifc"
        rapport = to_ifc(plan, chemin, validate=True)
        assert rapport.valide
        assert chemin.is_file()
        texte = chemin.read_text(encoding="utf-8")
        assert "ISO-10303-21" in texte
        assert "IFCSPACE" in texte


def test_taux_de_survie_avec_wilson() -> None:
    """`MILESTONE-6.md` §4 : 0 ≤ lo ≤ taux ≤ hi ≤ 1."""
    plans = [_plan_sain(), _plan_sain(), _plan_pathologique()]
    taux, (lo, hi) = survival_rate(plans)
    assert 0.0 <= lo <= taux <= hi <= 1.0
    assert taux == pytest.approx(2.0 / 3.0)


def test_wilson_aux_extremes() -> None:
    """Wilson reste dans [0, 1] pour 0/n et n/n."""
    lo, hi = intervalle_wilson(0, 10)
    assert 0.0 <= lo <= hi <= 1.0
    lo, hi = intervalle_wilson(10, 10)
    assert 0.0 <= lo <= hi <= 1.0


def test_to_ifc_refuse_pathologique(tmp_path: Path) -> None:
    chemin = tmp_path / "mauvais.ifc"
    rapport = to_ifc(_plan_pathologique(), chemin, validate=True)
    assert not rapport.valide
    assert not chemin.exists()
    assert rapport.moteur == "refuse"


def test_to_dxf_ecrit_lwpolyline(tmp_path: Path) -> None:
    chemin = tmp_path / "plan.dxf"
    to_dxf(_plan_sain(), chemin)
    texte = chemin.read_text(encoding="utf-8")
    assert "LWPOLYLINE" in texte
    assert "EOF" in texte


def test_to_dxf_leve_sur_pathologie(tmp_path: Path) -> None:
    with pytest.raises(InvariantViole):
        to_dxf(_plan_pathologique(), tmp_path / "x.dxf")


def test_pathologie_arete_nulle() -> None:
    diag = diagnostiquer(_plan_pathologique())
    assert any(p.startswith("arete_nulle:") for p in diag.pathologies)
    assert any(p.startswith("chevauchement:") for p in diag.pathologies)
