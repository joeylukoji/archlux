"""API publique gelée — `MILESTONE-6.md` §8 / version 1.0."""

from __future__ import annotations

import archlux
from archlux.types import Context, Orientation, Plan, Regulation, Room, Structure
from tests.properties.strategies import CONTEXTE_DEFAUT


def test_api_publique_stable() -> None:
    """Verrouille l'interface : toute suppression casse ce test."""
    attendu = {
        "legalize",
        "Plan",
        "Context",
        "Certificate",
        "Infeasible",
        "InvariantViolation",
        "light",
        "bench",
        "feasibility",
    }
    assert attendu <= set(archlux.__all__)


def test_feasibility_faisable() -> None:
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),
            Room(id="b", type="bedroom", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=CONTEXTE_DEFAUT.outline,
    )
    verdict = archlux.feasibility.is_feasible(
        plan, Structure(load_bearing_walls=()), CONTEXTE_DEFAUT
    )
    assert verdict
    assert verdict.certificate is None


def test_feasibility_infaisable_explique() -> None:
    contour = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=8.0, h=8.0),
            Room(id="b", type="living_room", x=8.0, y=0.0, w=8.0, h=8.0),
        ),
        walls=(),
        openings=(),
        outline=contour,
    )
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=contour,
        regulation=Regulation(min_areas=(), min_width=8.0),
    )
    verdict = archlux.feasibility.is_feasible(plan, ctx.structure, ctx)
    assert not verdict
    assert verdict.certificate is not None
    texte = verdict.certificate.explain()
    assert texte.startswith("Infeasible for this relative order")
    assert "verified exactly" in texte
    assert verdict.certificate.origins


def test_import_archlux_ne_charge_pas_torch() -> None:
    """Régression locale du contrat 1.0 (complète test_dependances)."""
    import subprocess
    import sys

    code = "import archlux, sys; assert 'torch' not in sys.modules"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0
