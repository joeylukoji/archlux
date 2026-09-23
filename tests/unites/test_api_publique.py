"""API publique gelée — `MILESTONE-6.md` §8 / version 1.0."""

from __future__ import annotations

import archlux
from archlux.types import Contexte, Orientation, Piece, Plan, Referentiel, Structure
from tests.proprietes.strategies import CONTEXTE_DEFAUT


def test_api_publique_stable() -> None:
    """Verrouille l'interface : toute suppression casse ce test."""
    attendu = {
        "legalize",
        "Plan",
        "Contexte",
        "Certificat",
        "Infaisable",
        "InvariantViole",
        "light",
        "bench",
        "feasibility",
    }
    assert attendu <= set(archlux.__all__)


def test_feasibility_faisable() -> None:
    plan = Plan(
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            Piece(id="b", type="chambre", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )
    verdict = archlux.feasibility.is_feasible(plan, Structure(murs_porteurs=()), CONTEXTE_DEFAUT)
    assert verdict
    assert verdict.certificat is None


def test_feasibility_infaisable_explique() -> None:
    contour = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
    plan = Plan(
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=8.0, h=8.0),
            Piece(id="b", type="sejour", x=8.0, y=0.0, w=8.0, h=8.0),
        ),
        murs=(),
        ouvertures=(),
        contour=contour,
    )
    ctx = Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=0.0),
        contour=contour,
        referentiel=Referentiel(aires_min=(), largeur_min=8.0),
    )
    verdict = archlux.feasibility.is_feasible(plan, ctx.structure, ctx)
    assert not verdict
    assert verdict.certificat is not None
    texte = verdict.certificat.expliquer()
    assert texte.startswith("Infaisable")
    assert verdict.certificat.origines


def test_import_archlux_ne_charge_pas_torch() -> None:
    """Régression locale du contrat 1.0 (complète test_dependances)."""
    import subprocess
    import sys

    code = "import archlux, sys; assert 'torch' not in sys.modules"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0
