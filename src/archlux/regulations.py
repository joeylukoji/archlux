"""Regulation presets: sourced thresholds, ready to use (PLAN.md 5.4).

A preset is a :class:`~archlux.types.Regulation` plus where each value comes from and,
as importantly, which rules of the same texts it does **not** check: the model only knows
minimum areas per room type and one minimum width, so a ceiling height, a volume or a
turning circle stays outside it. A preset is a sourced aid, not legal advice.

Examples
--------
>>> import archlux as ax
>>> fr = ax.preset("fr/new-collective-housing")
>>> fr.regulation.min_area("bedroom"), fr.regulation.min_width
(7.0, 0.9)
"""

from __future__ import annotations

from dataclasses import dataclass

from archlux.errors import InvalidInput
from archlux.types import Regulation

__all__ = ["PRESETS", "Preset", "Source", "preset"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Source:
    """One threshold of a preset and the text it comes from.

    Attributes
    ----------
    rule : str
        What the preset enforces, e.g. ``"living_room >= 9 m2"``.
    text : str
        The regulatory text, article included.
    provision : str
        The provision, in its language.
    verbatim : bool
        ``provision`` is quoted word for word from the official text; ``False`` when it
        was read from a secondary source and summarized, to check against the original.
    url : str
        Where to read it.
    """

    rule: str
    text: str
    provision: str
    verbatim: bool
    url: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Preset:
    """A sourced regulation.

    Attributes
    ----------
    name : str
        Identifier, ``"<country>/<use>"``.
    regulation : Regulation
        The thresholds the solver and the proof enforce.
    sources : tuple of Source
        One entry per threshold.
    not_checked : tuple of str
        Rules of the same texts the model cannot express; checking them is left to the
        user.
    checked_on : str
        ISO date the sources were last read.
    """

    name: str
    regulation: Regulation
    sources: tuple[Source, ...]
    not_checked: tuple[str, ...]
    checked_on: str


_DECENCY = "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000043842463"
_ACCESSIBILITY = "https://www.legifrance.gouv.fr/loda/article_lc/LEGIARTI000031830907"
_RSD = "https://www.occitanie.developpement-durable.gouv.fr/IMG/pdf/05_application_rsd.pdf"

_FR_NEW_COLLECTIVE_HOUSING = Preset(
    name="fr/new-collective-housing",
    regulation=Regulation(min_areas=(("living_room", 9.0), ("bedroom", 7.0)), min_width=0.90),
    sources=(
        Source(
            rule="living_room >= 9 m2",
            text="Décret n° 2002-120 du 30 janvier 2002 (logement décent), article 4",
            provision=(
                "Le logement dispose au moins d'une pièce principale ayant soit une surface "
                "habitable au moins égale à 9 mètres carrés et une hauteur sous plafond au "
                "moins égale à 2,20 mètres, soit un volume habitable au moins égal à 20 "
                "mètres cubes."
            ),
            verbatim=True,
            url=_DECENCY,
        ),
        Source(
            rule="bedroom >= 7 m2",
            text="Règlement sanitaire départemental type (circulaire du 9 août 1978), article 40.1",
            provision=(
                "L'une au moins des pièces principales doit avoir une surface supérieure à "
                "9 m², les autres pièces d'habitation ne peuvent avoir une surface "
                "inférieure à 7 m²."
            ),
            verbatim=False,
            url=_RSD,
        ),
        Source(
            rule="min_width >= 0.90 m",
            text=(
                "Arrêté du 24 décembre 2015 (accessibilité des bâtiments d'habitation "
                "collectifs lors de leur construction), article 11"
            ),
            provision="Largeur minimale des circulations intérieures : 0,90 m.",
            verbatim=False,
            url=_ACCESSIBILITY,
        ),
    ),
    not_checked=(
        "ceiling height (2.20 m, decree 2002-120 art. 4) and habitable volume (20 m3)",
        "parts of a room narrower than 2 m left out of its area (RSD type art. 40.1)",
        "door widths: 0.83 m clear at the entrance, 0.77 m inside (arrêté 2015 art. 11)",
        "bedroom and shower-room clearances around the bed and turning circle "
        "(arrêté 2015 art. 13 and following)",
        "area per occupant of the dwelling as a whole",
        "the departmental RSD in force, which may be stricter than the model text",
    ),
    checked_on="2026-10-10",
)

PRESETS: dict[str, Preset] = {_FR_NEW_COLLECTIVE_HOUSING.name: _FR_NEW_COLLECTIVE_HOUSING}
"""Every preset, by name."""


def preset(name: str) -> Preset:
    """The preset of that name.

    Parameters
    ----------
    name : str
        A key of :data:`PRESETS`, e.g. ``"fr/new-collective-housing"``.

    Returns
    -------
    Preset
        The thresholds, their sources and what they leave unchecked.

    Raises
    ------
    InvalidInput
        No preset has that name; the message lists the known ones.
    """
    try:
        return PRESETS[name]
    except KeyError:
        raise InvalidInput(
            "name", f"unknown preset {name!r}", f"known: {sorted(PRESETS)}"
        ) from None
