"""Physical reference: point-in-time illuminance by Radiance backward ray tracing.

**Off the critical path** (``ARCHITECTURE.md`` §2): the core never imports this module,
and nothing in the CI requires the Radiance binaries. When ``oconv``, ``rtrace`` and
``gensky`` are on ``PATH``, :class:`RadianceReference` builds a scene from the decision
vector and the glazing, traces a grid of work-plane sensors and returns a
:class:`~archlux.light.reference.ReferenceMeasure` with ``kind="physical"``. When they are
not, :meth:`RadianceReference.measure` raises
:class:`~archlux.light.reference.ReferenceUnavailable`: it never returns a number it did
not measure.

What it measures, exactly
-------------------------
The **area-weighted mean work-plane illuminance, in lux**, of the plan under one CIE sky
(``gensky``) at one instant, plus the mean per room. It is not an LM-83 sDA, which needs
an annual climate-based simulation (``rfluxmtx`` / ``dctimestep`` over an EPW file). A
surrogate trained on another indicator is compared with it through rank and linear
correlation only: absolute errors need the same unit (:mod:`archlux.light.evaluation`).

Scene model (the assumptions a reviewer must see)
-------------------------------------------------
- every room is a closed box ``w x h x ceiling_height``; partitions are opaque, two
  rooms exchange no light;
- light enters only through the openings of ``glazing``; an opening is attached to a
  room edge when its segment lies on that edge's line (within ``snap_m``) and overlaps
  it. A plan without openings is refused: its illuminance would be zero by construction;
- no urban mask, no furniture, no frame; Lambertian reflectances; one glazing
  transmittance;
- the plan is rotated **counterclockwise** by the azimuth, the convention of
  :class:`~archlux.light.analytic.AnalyticSurrogate` (``+y`` is north at ``0``);
  Radiance's own frame has ``+X`` east, ``+Y`` north, ``+Z`` up.

Command run (from a temporary directory)::

    oconv sky.rad scene.rad > scene.oct
    rtrace -h -I+ -ab 5 -ad 1024 -as 512 -ar 256 -aa 0.1 scene.oct < sensors.pts
"""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from archlux.light.reference import ReferenceKind, ReferenceMeasure, ReferenceUnavailable
from archlux.light.tokens import FIELDS_PER_ROOM

if TYPE_CHECKING:
    from archlux.arrays import FloatVector
    from archlux.light.protocol import Glazing
    from archlux.types import Orientation

__all__ = [
    "BINARIES",
    "RadianceReference",
    "RadianceSettings",
    "glass_transmissivity",
    "radiance_available",
    "scene_description",
    "sensor_grid",
]

BINARIES: tuple[str, ...] = ("oconv", "rtrace", "gensky")
"""Executables the reference needs on ``PATH``."""

_LUMINOUS_EFFICACY = 179.0
"""White-light efficacy of Radiance, lm/W: ``lux = 179 (0.265 R + 0.670 G + 0.065 B)``."""

_RGB_WEIGHTS = (0.265, 0.670, 0.065)


@dataclass(frozen=True, slots=True)
class RadianceSettings:
    """Every parameter of a Radiance run; all of them are written into the measure.

    Attributes
    ----------
    month, day, hour : int, int, float
        Instant of the sky, local standard time.
    latitude, longitude, meridian : float
        Site, in degrees; longitude and meridian **east-positive** here (converted to
        Radiance's west-positive convention when the sky is written). Default: Bern.
    sky : str
        ``gensky`` sky flag: ``"+s"`` clear with sun, ``"-c"`` overcast, ``"+i"``
        intermediate with sun.
    ceiling_height, work_plane, grid_m : float
        Room height, sensor height and sensor spacing, in metres.
    floor, wall, ceiling : float
        Lambertian reflectances.
    transmittance : float
        Normal-incidence visible transmittance of the glazing.
    ambient_bounces, ambient_divisions, ambient_supersamples, ambient_resolution : int
        ``-ab``, ``-ad``, ``-as``, ``-ar``.
    ambient_accuracy : float
        ``-aa``.
    snap_m : float
        Distance under which an opening is considered to lie on a room edge.
    """

    month: int = 3
    day: int = 21
    hour: float = 12.0
    latitude: float = 46.95
    longitude: float = 7.44
    meridian: float = 15.0
    sky: str = "+s"
    ceiling_height: float = 2.70
    work_plane: float = 0.80
    grid_m: float = 0.50
    floor: float = 0.20
    wall: float = 0.50
    ceiling: float = 0.80
    transmittance: float = 0.60
    ambient_bounces: int = 5
    ambient_divisions: int = 1024
    ambient_supersamples: int = 512
    ambient_resolution: int = 256
    ambient_accuracy: float = 0.10
    snap_m: float = 0.15

    def as_parameters(self) -> tuple[tuple[str, str], ...]:
        """Every setting as sorted ``(name, value)`` strings, for the measure.

        Returns
        -------
        tuple of tuple of str
            The settings, sorted by name.
        """
        names = sorted(self.__slots__)
        return tuple((name, str(getattr(self, name))) for name in names)

    def rtrace_options(self) -> list[str]:
        """Ambient options of ``rtrace``.

        Returns
        -------
        list of str
            ``-ab``, ``-ad``, ``-as``, ``-ar`` and ``-aa`` with their values.
        """
        return [
            "-ab",
            str(self.ambient_bounces),
            "-ad",
            str(self.ambient_divisions),
            "-as",
            str(self.ambient_supersamples),
            "-ar",
            str(self.ambient_resolution),
            "-aa",
            str(self.ambient_accuracy),
        ]


def radiance_available() -> bool:
    """Say whether every binary of :data:`BINARIES` is on ``PATH``.

    Returns
    -------
    bool
        ``True`` when the reference can run here.
    """
    return all(shutil.which(name) is not None for name in BINARIES)


def glass_transmissivity(transmittance: float) -> float:
    """Convert a normal transmittance into the transmissivity of Radiance's ``glass``.

    Parameters
    ----------
    transmittance : float
        Normal-incidence transmittance, in ``]0, 1[``.

    Returns
    -------
    float
        Transmissivity ``tn`` (Radiance reference manual, ``glass`` material).
    """
    t = transmittance
    return (math.sqrt(0.8402528435 + 0.0072522239 * t * t) - 0.9166530661) / 0.0036261119 / t


def _rotate(points: np.ndarray, orientation: Orientation) -> np.ndarray:
    """Rotate plan points counterclockwise by the azimuth, about the origin.

    Parameters
    ----------
    points : numpy.ndarray
        Shape ``(n, 2)`` or ``(n, 3)``; only the first two columns turn.
    orientation : Orientation
        Azimuth of the plan.

    Returns
    -------
    numpy.ndarray
        Rotated copy.
    """
    theta = math.radians(orientation.deg)
    c, s = math.cos(theta), math.sin(theta)
    out = np.array(points, dtype=float, copy=True)
    x, y = out[:, 0].copy(), out[:, 1].copy()
    out[:, 0] = c * x - s * y
    out[:, 1] = s * x + c * y
    return out


def _rooms(x: FloatVector) -> np.ndarray:
    """Reshape the decision vector into one ``(x, y, w, h)`` row per room.

    Parameters
    ----------
    x : numpy.ndarray
        Decision vector.

    Returns
    -------
    numpy.ndarray
        Shape ``(n_rooms, 4)``.
    """
    vector = np.asarray(x, dtype=float).ravel()
    return vector[: vector.size // FIELDS_PER_ROOM * FIELDS_PER_ROOM].reshape(-1, 4)


def _edges(room: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """The four edges of a room rectangle, as pairs of 2-D points.

    Parameters
    ----------
    room : numpy.ndarray
        ``(x, y, w, h)``.

    Returns
    -------
    list of tuple of numpy.ndarray
        Bottom, right, top, left edges.
    """
    x0, y0, w, h = (float(v) for v in room)
    corners = [np.array(p) for p in ((x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h))]
    return [(corners[i], corners[(i + 1) % 4]) for i in range(4)]


def _project(
    edge: tuple[np.ndarray, np.ndarray], a: np.ndarray, b: np.ndarray, snap: float
) -> tuple[float, float] | None:
    """Interval of the segment ``ab`` along ``edge``, or ``None`` if it is not on it.

    Parameters
    ----------
    edge : tuple of numpy.ndarray
        Edge of the room, start and end.
    a, b : numpy.ndarray
        Ends of the opening.
    snap : float
        Largest distance between the opening and the edge line.

    Returns
    -------
    tuple of float or None
        ``(t0, t1)`` in metres from the edge start, clipped to the edge.
    """
    p0, p1 = edge
    length = float(np.linalg.norm(p1 - p0))
    if length <= 0.0:
        return None
    u = (p1 - p0) / length
    normal = np.array([-u[1], u[0]])
    if max(abs(float(np.dot(a - p0, normal))), abs(float(np.dot(b - p0, normal)))) > snap:
        return None
    ta, tb = sorted((float(np.dot(a - p0, u)), float(np.dot(b - p0, u))))
    t0, t1 = max(ta, 0.0), min(tb, length)
    return (t0, t1) if t1 > t0 else None


def _windows_on_edge(
    edge: tuple[np.ndarray, np.ndarray], glazing: Glazing, snap: float
) -> list[tuple[float, float, float, float]]:
    """Openings lying on an edge, as ``(t0, t1, sill, head)``.

    Parameters
    ----------
    edge : tuple of numpy.ndarray
        Edge of the room.
    glazing : Glazing
        Openings and their walls.
    snap : float
        Largest distance between an opening and the edge line.

    Returns
    -------
    list of tuple of float
        One entry per opening on the edge, sorted by ``t0``.
    """
    walls = {wall.id: wall for wall in glazing.walls}
    found = []
    for opening in glazing.openings:
        wall = walls.get(opening.wall_id)
        if wall is None:
            continue
        a, b = (np.array(p, dtype=float) for p in opening.absolute_segment(wall))
        span = _project(edge, a, b, snap)
        if span is not None:
            found.append((span[0], span[1], opening.sill_height, opening.head_height))
    return sorted(found)


def _wall_pieces(
    length: float, windows: list[tuple[float, float, float, float]], height: float
) -> list[tuple[float, float, float, float, str]]:
    """Split a wall face into opaque pieces and glass panes.

    Parameters
    ----------
    length : float
        Length of the wall face.
    windows : list of tuple of float
        ``(t0, t1, sill, head)``, sorted, not overlapping.
    height : float
        Ceiling height.

    Returns
    -------
    list of tuple
        ``(t0, t1, z0, z1, material)`` rectangles covering the face.
    """
    pieces: list[tuple[float, float, float, float, str]] = []
    cursor = 0.0
    for t0, t1, sill, head in windows:
        t0 = max(t0, cursor)
        if t1 <= t0:
            continue
        if t0 > cursor:
            pieces.append((cursor, t0, 0.0, height, "wall_mat"))
        pieces.append((t0, t1, 0.0, sill, "wall_mat"))
        pieces.append((t0, t1, sill, head, "glass_mat"))
        pieces.append((t0, t1, head, height, "wall_mat"))
        cursor = t1
    if cursor < length:
        pieces.append((cursor, length, 0.0, height, "wall_mat"))
    return [p for p in pieces if p[3] > p[2] and p[1] > p[0]]


def _polygon(name: str, material: str, vertices: np.ndarray) -> str:
    """One Radiance ``polygon`` primitive.

    Parameters
    ----------
    name : str
        Identifier of the primitive.
    material : str
        Modifier.
    vertices : numpy.ndarray
        Shape ``(n, 3)``, already in Radiance's frame.

    Returns
    -------
    str
        The primitive, ending with a newline.
    """
    coords = " ".join(f"{v:.6f}" for v in vertices.ravel())
    return f"{material} polygon {name}\n0\n0\n{vertices.size} {coords}\n"


def _room_faces(
    index: int, room: np.ndarray, glazing: Glazing, settings: RadianceSettings
) -> tuple[list[tuple[str, str, np.ndarray]], int]:
    """Floor, ceiling and wall pieces of one room, in plan coordinates.

    Parameters
    ----------
    index : int
        Index of the room, used in primitive names.
    room : numpy.ndarray
        ``(x, y, w, h)``.
    glazing : Glazing
        Openings of the plan.
    settings : RadianceSettings
        Heights and snapping distance.

    Returns
    -------
    tuple
        ``(faces, n_panes)``: faces as ``(name, material, vertices)``, and the number of
        glass panes the room received.
    """
    x0, y0, w, h = (float(v) for v in room)
    height = settings.ceiling_height
    flat = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    faces = [
        (f"r{index}_floor", "floor_mat", np.array([(px, py, 0.0) for px, py in flat])),
        (f"r{index}_ceiling", "ceiling_mat", np.array([(px, py, height) for px, py in flat])),
    ]
    panes = 0
    for e, edge in enumerate(_edges(room)):
        p0, p1 = edge
        length = float(np.linalg.norm(p1 - p0))
        u = (p1 - p0) / length
        windows = _windows_on_edge(edge, glazing, settings.snap_m)
        for k, (t0, t1, z0, z1, material) in enumerate(_wall_pieces(length, windows, height)):
            a, b = p0 + t0 * u, p0 + t1 * u
            quad = np.array([(*a, z0), (*b, z0), (*b, z1), (*a, z1)])
            faces.append((f"r{index}_e{e}_{k}", material, quad))
            panes += material == "glass_mat"
    return faces, panes


def _materials(settings: RadianceSettings) -> str:
    """Material definitions of the scene.

    Parameters
    ----------
    settings : RadianceSettings
        Reflectances and transmittance.

    Returns
    -------
    str
        ``plastic`` and ``glass`` primitives.
    """
    tn = glass_transmissivity(settings.transmittance)
    lines = [
        f"void plastic {name} 0 0 5 {rho} {rho} {rho} 0 0"
        for name, rho in (
            ("floor_mat", settings.floor),
            ("wall_mat", settings.wall),
            ("ceiling_mat", settings.ceiling),
        )
    ]
    lines.append(f"void glass glass_mat 0 0 3 {tn:.6f} {tn:.6f} {tn:.6f}")
    return "\n".join(lines) + "\n"


def scene_description(
    x: FloatVector, orientation: Orientation, glazing: Glazing, settings: RadianceSettings
) -> tuple[str, int]:
    """Radiance scene of the plan: materials, then every face, rotated.

    Parameters
    ----------
    x : numpy.ndarray
        Decision vector, ``(x, y, w, h)`` per room.
    orientation : Orientation
        Azimuth of the plan.
    glazing : Glazing
        Openings of the plan.
    settings : RadianceSettings
        Geometry and material settings.

    Returns
    -------
    tuple of (str, int)
        The scene text and the number of glass panes placed. Zero panes means no
        opening matched any room edge.
    """
    parts = [_materials(settings)]
    panes = 0
    for i, room in enumerate(_rooms(x)):
        faces, n = _room_faces(i, room, glazing, settings)
        panes += n
        for name, material, vertices in faces:
            parts.append(_polygon(name, material, _rotate(vertices, orientation)))
    return "".join(parts), panes


def sensor_grid(
    x: FloatVector, orientation: Orientation, settings: RadianceSettings
) -> tuple[np.ndarray, np.ndarray]:
    """Work-plane sensors, rotated, and the room each sensor belongs to.

    Parameters
    ----------
    x : numpy.ndarray
        Decision vector.
    orientation : Orientation
        Azimuth of the plan.
    settings : RadianceSettings
        Grid spacing and work-plane height.

    Returns
    -------
    tuple of numpy.ndarray
        ``(points, owner)``: points of shape ``(n, 6)`` (position, upward direction) in
        Radiance's frame, and the room index of each point. A room smaller than one cell
        gets one sensor at its centre.
    """
    rows, owner = [], []
    g = settings.grid_m
    for i, (x0, y0, w, h) in enumerate(_rooms(x)):
        nx, ny = max(int(w // g), 1), max(int(h // g), 1)
        xs = x0 + (np.arange(nx) + 0.5) * (w / nx)
        ys = y0 + (np.arange(ny) + 0.5) * (h / ny)
        for px in xs:
            for py in ys:
                rows.append((px, py, settings.work_plane, 0.0, 0.0, 1.0))
                owner.append(i)
    points = _rotate(np.array(rows, dtype=float).reshape(-1, 6), orientation)
    return points, np.array(owner, dtype=int)


def _sky(settings: RadianceSettings) -> str:
    """Sky file: ``gensky`` call plus sky and ground glow sources.

    Parameters
    ----------
    settings : RadianceSettings
        Instant, site and sky type.

    Returns
    -------
    str
        Content of ``sky.rad``. Longitude and meridian are negated: Radiance counts
        them west-positive.
    """
    s = settings
    return (
        f"!gensky {s.month} {s.day} {s.hour} {s.sky} -a {s.latitude} "
        f"-o {-s.longitude} -m {-s.meridian}\n"
        "skyfunc glow sky_glow 0 0 4 1 1 1 0\n"
        "sky_glow source sky 0 0 4 0 0 1 180\n"
        "skyfunc glow ground_glow 0 0 4 1 1 1 0\n"
        "ground_glow source ground 0 0 4 0 0 -1 180\n"
    )


def _illuminance(output: str) -> np.ndarray:
    """Convert ``rtrace -I+`` RGB irradiances into illuminances, in lux.

    Parameters
    ----------
    output : str
        Standard output of ``rtrace -h``, one ``R G B`` triple per line.

    Returns
    -------
    numpy.ndarray
        One illuminance per sensor.
    """
    rgb = np.array([[float(v) for v in line.split()[:3]] for line in output.splitlines()])
    lux: np.ndarray = _LUMINOUS_EFFICACY * (rgb.reshape(-1, 3) @ np.array(_RGB_WEIGHTS))
    return lux


@dataclass(frozen=True, slots=True)
class RadianceReference:
    """Physical reference: Radiance work-plane illuminance under one CIE sky.

    Attributes
    ----------
    settings : RadianceSettings
        Every parameter of the run, copied into each measure.
    """

    settings: RadianceSettings = RadianceSettings()

    @property
    def kind(self) -> ReferenceKind:
        """Always ``"physical"``.

        Returns
        -------
        ReferenceKind
            ``"physical"``.
        """
        return "physical"

    @property
    def unit(self) -> str:
        """Lux.

        Returns
        -------
        str
            ``"lux"``.
        """
        return "lux"

    def measure(
        self, x: FloatVector, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> ReferenceMeasure:
        """Trace the plan and return its area-weighted mean illuminance.

        Parameters
        ----------
        x
            Decision vector, ``(x, y, w, h)`` per room.
        orientation
            Azimuth of the plan.
        glazing
            Openings of the plan. Required.

        Returns
        -------
        ReferenceMeasure
            ``kind="physical"``, ``unit="lux"``, one mean per room.

        Raises
        ------
        ReferenceUnavailable
            A binary is missing, the plan has no opening, no opening lies on a room edge,
            or Radiance failed.
        """
        if not radiance_available():
            missing = [name for name in BINARIES if shutil.which(name) is None]
            raise ReferenceUnavailable(f"Radiance binaries not on PATH: {missing}")
        if glazing is None or glazing.empty:
            raise ReferenceUnavailable("no opening: the illuminance would be zero by design")
        scene, panes = scene_description(x, orientation, glazing, self.settings)
        if panes == 0:
            raise ReferenceUnavailable("no opening lies on a room edge")
        points, owner = sensor_grid(x, orientation, self.settings)
        lux = self._trace(scene, points)
        rooms = _rooms(x)
        per_room = tuple(float(lux[owner == i].mean()) for i in range(rooms.shape[0]))
        areas = rooms[:, 2] * rooms[:, 3]
        value = float(np.dot(per_room, areas) / max(float(areas.sum()), 1e-12))
        return ReferenceMeasure(
            value=value,
            unit=self.unit,
            kind=self.kind,
            engine=f"Radiance ({_version()})",
            parameters=self.settings.as_parameters(),
            per_room=per_room,
        )

    def _trace(self, scene: str, points: np.ndarray) -> np.ndarray:
        """Run ``oconv`` and ``rtrace`` in a temporary directory.

        Parameters
        ----------
        scene : str
            Content of ``scene.rad``.
        points : numpy.ndarray
            Sensors, shape ``(n, 6)``.

        Returns
        -------
        numpy.ndarray
            Illuminance of each sensor, in lux.

        Raises
        ------
        ReferenceUnavailable
            If a Radiance command fails.
        """
        with tempfile.TemporaryDirectory(prefix="archlux-rad-") as tmp:
            folder = Path(tmp)
            (folder / "scene.rad").write_text(scene, encoding="utf-8")
            (folder / "sky.rad").write_text(_sky(self.settings), encoding="utf-8")
            sensors = "\n".join(" ".join(f"{v:.6f}" for v in row) for row in points)
            try:
                octree = subprocess.run(
                    ["oconv", "sky.rad", "scene.rad"], cwd=folder, capture_output=True, check=True
                ).stdout
                (folder / "scene.oct").write_bytes(octree)
                traced = subprocess.run(
                    ["rtrace", "-h", "-I+", *self.settings.rtrace_options(), "scene.oct"],
                    cwd=folder,
                    input=sensors + "\n",
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout
            except subprocess.CalledProcessError as failed:
                raise ReferenceUnavailable(f"Radiance failed: {failed.stderr!r}") from failed
        return _illuminance(traced)


def _version() -> str:
    """Version string of ``rtrace``, or ``"unknown"``.

    Returns
    -------
    str
        First line of ``rtrace -version``.
    """
    try:
        done = subprocess.run(["rtrace", "-version"], capture_output=True, text=True, check=False)
    except OSError:
        return "unknown"
    return (
        (done.stdout or done.stderr).strip().splitlines()[0] if done.returncode == 0 else "unknown"
    )
