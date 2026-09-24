"""Rendu textuel du certificat. Les deux natures de garantie restent séparées.

Aucune ligne du rapport ne mélange l'exact et le probabiliste, et aucun score composite
ne les agrège : un lecteur doit pouvoir dire, pour chaque chiffre, s'il s'agit d'une
preuve ou d'une prédiction.
"""

from __future__ import annotations

from archlux._version import __version__
from archlux.types import BornePerformance, Certificat, Manifeste, PreuveGeometrique

__all__ = ["rendre"]

_HORS_PERIMETRE = (
    "Confort d'été, systèmes techniques, matériaux — hors périmètre "
    "(oracle gelé split-flux, pas un sDA LM-83)"
)


def _version() -> str:
    """Version of the source code, never stale install metadata."""
    return __version__


def _fmt(valeur: float, digits: int = 2) -> str:
    return f"{valeur:.{digits}f}".replace(".", ",")


def _verdict(ok: bool) -> str:
    return "verifie" if ok else "echec"


def _section_geometrie(preuve: PreuveGeometrique) -> str:
    chev = "aucun" if not preuve.chevauchement else "present"
    jours = "aucun" if not preuve.jours else "present"
    surfaces = "ok" if preuve.surfaces_ok else "insuffisantes"
    structure = "oui" if preuve.structure_preservee else "non"
    deplacement = f"{_fmt(preuve.deplacement_max)} m"
    return (
        "GEOMETRIE                                       [EXACT]\n"
        f"  Chevauchement          {chev:<13} {_verdict(not preuve.chevauchement)}\n"
        f"  Jours                  {jours:<13} {_verdict(not preuve.jours)}\n"
        f"  Surfaces minimales     {surfaces:<13} {_verdict(preuve.surfaces_ok)}\n"
        f"  Structure preservee    {structure:<13} {_verdict(preuve.structure_preservee)}\n"
        f"  Deplacement maximal    {deplacement}"
    )


def _section_performance(borne: BornePerformance | None) -> str:
    if borne is None:
        corps = "  NON EVALUABLE — pas de calibration, ou dérive (échangeabilité rompue)"
        bandeau = "[PREDICTION — non évaluable]"
    else:
        pct = f"{borne.couverture * 100.0:.0f}"
        if borne.coverage_guaranteed:
            bandeau = f"[PREDICTION — couverture {pct} %]"
        else:
            # Batch 1.6: the optimizer chose this plan, the coverage is not guaranteed.
            bandeau = "[PREDICTION — plan selectionne, couverture NON garantie]"
        if borne.indicateur == "ASE":
            ligne = (
                f"  {borne.indicateur}   <= {_fmt(borne.borne_sup)}   "
                f"(predit {_fmt(borne.valeur)}, "
                f"marge {_fmt(borne.borne_sup - borne.valeur)})"
            )
        else:
            ligne = (
                f"  {borne.indicateur}   >= {_fmt(borne.borne_inf)}   "
                f"(predit {_fmt(borne.valeur)}, "
                f"marge {_fmt(borne.valeur - borne.borne_inf)})"
            )
        corps = f"{ligne}\n  calibration : {borne.n_calibration} évaluations de l'oracle gelé"
        if not borne.coverage_guaranteed:
            corps += (
                f"\n  regime selectionne : plan choisi par l'optimiseur ; la couverture "
                f"nominale de {pct} % suppose un plan echangeable avec la calibration"
                "\n  (malediction du vainqueur). Reevaluer ce plan avec l'oracle avant "
                "de publier une couverture."
            )
    return f"PERFORMANCE                        {bandeau}\n{corps}"


def _section_diagnostic(duaux: tuple[tuple[str, float], ...]) -> str:
    if not duaux:
        corps = "  (aucune contrainte active au-delà du seuil)"
    else:
        corps = "\n".join(f"  {libelle}" for libelle, _prix in duaux)
    return f"DIAGNOSTIC\n{corps}"


def _en_tete(manifeste: Manifeste | None) -> str:
    paquet = _version()
    if manifeste is None:
        return f"CERTIFICAT                              archlux {paquet}"
    return (
        f"CERTIFICAT                              archlux {manifeste.version}     "
        f"graine {manifeste.graine}"
    )


def rendre(certificat: Certificat) -> str:
    """Rendre le certificat en texte lisible.

    Returns
    -------
    str
        Rapport à deux natures. Si ``certificat.performance`` est ``None``, la section
        performance affiche ``NON EVALUABLE`` — jamais un intervalle par défaut. La
        section ``NON EVALUABLE`` de périmètre est **toujours** présente.
    """
    parties = [
        _en_tete(certificat.manifeste),
        "",
        _section_geometrie(certificat.geometrie),
        "",
        _section_performance(certificat.performance),
        "",
        _section_diagnostic(certificat.duaux),
        "",
        "NON EVALUABLE",
        f"  {_HORS_PERIMETRE}",
    ]
    return "\n".join(parties) + "\n"
