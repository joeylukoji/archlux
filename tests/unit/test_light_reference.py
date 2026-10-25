"""Surrogate against reference: the two are never confused (spec 1.3).

Radiance itself is not installed in CI: the scene builder is tested as pure text, the
missing-binary path is tested to raise, and one integration test runs only where
``oconv``/``rtrace``/``gensky`` are on ``PATH``.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from archlux.light import radiance
from archlux.light.protocol import Glazing
from archlux.light.radiance import (
    RadianceReference,
    RadianceSettings,
    glass_transmissivity,
    scene_description,
    sensor_grid,
)
from archlux.light.reference import (
    ClosedFormReference,
    ReferenceEvaluator,
    ReferenceUnavailable,
)
from archlux.light.split_flux import SplitFluxOracle
from archlux.types import Opening, Orientation, Wall

X = np.array([0.0, 0.0, 6.0, 4.5, 6.0, 0.0, 6.0, 4.5])
SOUTH_WALL = Wall(id="s", a=(0.0, 0.0), b=(12.0, 0.0))
WINDOW = Opening(id="w", wall_id="s", s=0.25, relative_width=0.2)
GLAZING = Glazing(walls=(SOUTH_WALL,), openings=(WINDOW,))
NORTH = Orientation(deg=0.0)


def test_the_closed_form_reference_says_it_is_not_physical() -> None:
    oracle = SplitFluxOracle()
    measure = ClosedFormReference(oracle).measure(X, NORTH)
    assert measure.kind == "closed_form"
    assert measure.value == oracle.evaluate(X, NORTH)
    assert "not a simulation" in measure.engine


def test_the_evaluator_adapter_returns_the_measured_value() -> None:
    reference = ClosedFormReference(SplitFluxOracle())
    assert ReferenceEvaluator(reference).evaluate(X, NORTH) == reference.measure(X, NORTH).value


def test_radiance_without_binaries_raises_instead_of_inventing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(radiance.shutil, "which", lambda name: None)
    with pytest.raises(ReferenceUnavailable, match="not on PATH"):
        RadianceReference().measure(X, NORTH, glazing=GLAZING)


def test_radiance_refuses_a_plan_without_openings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(radiance, "radiance_available", lambda: True)
    with pytest.raises(ReferenceUnavailable, match="no opening"):
        RadianceReference().measure(X, NORTH, glazing=None)


def test_an_opening_off_every_room_edge_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(radiance, "radiance_available", lambda: True)
    far = Glazing(walls=(Wall(id="s", a=(0.0, -5.0), b=(12.0, -5.0)),), openings=(WINDOW,))
    with pytest.raises(ReferenceUnavailable, match="room edge"):
        RadianceReference().measure(X, NORTH, glazing=far)


def test_the_scene_places_one_pane_on_the_south_edge_of_the_first_room() -> None:
    scene, panes = scene_description(X, NORTH, GLAZING, RadianceSettings())
    assert panes == 1  # centred at x = 3, 2.4 m wide: inside room 0 only
    assert scene.count("glass_mat polygon") == 1
    assert scene.startswith("void plastic floor_mat")


def test_the_sky_converts_east_longitudes_to_radiance_west_positive() -> None:
    sky = radiance._sky(RadianceSettings(longitude=7.44, meridian=15.0))
    assert "-o -7.44 -m -15.0" in sky


def test_rotation_is_counterclockwise_like_the_analytic_surrogate() -> None:
    turned = radiance._rotate(np.array([[1.0, 0.0, 2.0]]), Orientation(deg=90.0))
    assert np.allclose(turned, [[0.0, 1.0, 2.0]])


def test_sensor_grid_covers_each_room() -> None:
    points, owner = sensor_grid(X, NORTH, RadianceSettings(grid_m=0.5))
    assert points.shape == (2 * 12 * 9, 6)
    assert set(owner.tolist()) == {0, 1}
    assert np.allclose(points[:, 2], 0.8) and np.allclose(points[:, 5], 1.0)


def test_glass_transmissivity_matches_the_radiance_formula() -> None:
    assert glass_transmissivity(0.88) == pytest.approx(0.96, abs=0.005)


def test_rgb_irradiance_becomes_lux() -> None:
    assert radiance._illuminance("1 1 1\n2 2 2\n").tolist() == pytest.approx([179.0, 358.0])


@given(
    length=st.floats(1.0, 20.0),
    start=st.floats(0.0, 0.8),
    width=st.floats(0.05, 0.5),
    sill=st.floats(0.0, 1.2),
    head=st.floats(1.3, 2.6),
)
def test_wall_pieces_tile_the_wall_face_exactly(
    length: float, start: float, width: float, sill: float, head: float
) -> None:
    """Property: opaque pieces plus panes cover the face, without overlap."""
    t0, t1 = start * length, min((start + width) * length, length)
    pieces = radiance._wall_pieces(length, [(t0, t1, sill, head)], 2.7)
    area = sum((b - a) * (z1 - z0) for a, b, z0, z1, _ in pieces)
    assert area == pytest.approx(length * 2.7)
    glass = [p for p in pieces if p[4] == "glass_mat"]
    assert len(glass) == 1
    assert (glass[0][1] - glass[0][0]) * (head - sill) == pytest.approx((t1 - t0) * (head - sill))


@pytest.mark.skipif(not radiance.radiance_available(), reason="Radiance not installed")
def test_radiance_measures_a_glazed_plan_when_installed() -> None:  # pragma: no cover
    settings = RadianceSettings(ambient_bounces=1, ambient_divisions=128, grid_m=1.0)
    measure = RadianceReference(settings).measure(X, NORTH, glazing=GLAZING)
    assert measure.kind == "physical" and measure.unit == "lux"
    assert measure.value > 0.0 and math.isfinite(measure.value)
    assert measure.per_room[0] > measure.per_room[1]  # only room 0 has a window
