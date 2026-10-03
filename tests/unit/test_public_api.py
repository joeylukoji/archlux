"""Frozen public API: `MILESTONE-6.md` §8 / version 1.0."""

from __future__ import annotations

import archlux
from archlux.types import Context, Orientation, Plan, Regulation, Room, Structure
from tests.properties.strategies import DEFAULT_CONTEXT


def test_stable_public_api() -> None:
    """Locks the interface: any removal breaks this test."""
    expected = {
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
    assert expected <= set(archlux.__all__)


def test_feasibility_feasible() -> None:
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),
            Room(id="b", type="bedroom", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )
    verdict = archlux.feasibility.is_feasible(
        plan, Structure(load_bearing_walls=()), DEFAULT_CONTEXT
    )
    assert verdict
    assert verdict.certificate is None


def test_feasibility_infeasible_explained() -> None:
    outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=8.0, h=8.0),
            Room(id="b", type="living_room", x=8.0, y=0.0, w=8.0, h=8.0),
        ),
        walls=(),
        openings=(),
        outline=outline,
    )
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=outline,
        regulation=Regulation(min_areas=(), min_width=8.0),
    )
    verdict = archlux.feasibility.is_feasible(plan, ctx.structure, ctx)
    assert not verdict
    assert verdict.certificate is not None
    text = verdict.certificate.explain()
    assert text.startswith("Infeasible for this relative order")
    assert "verified exactly" in text
    assert verdict.certificate.origins


def test_import_archlux_does_not_load_torch() -> None:
    """Local regression test of the 1.0 contract (completes test_dependencies)."""
    import subprocess
    import sys

    code = "import archlux, sys; assert 'torch' not in sys.modules"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0
