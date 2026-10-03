"""Evaluation protocol. Leaf of the tree: nothing imports this package."""

from archlux._deprecation import Alias, lazy_aliases
from archlux.bench.manifest import emit
from archlux.bench.protocol import Split, compare, load_split
from archlux.bench.report import BenchReport, OrientationStratum, report
from archlux.bench.run import Manifest, RawRow, Result, run
from archlux.bench.seeds import derive
from archlux.bench.stats import Interval, holm, paired_bootstrap, power, tost
from archlux.types import ModelTrace

__all__ = [
    "BenchReport",
    "Interval",
    "Manifest",
    "ModelTrace",
    "OrientationStratum",
    "RawRow",
    "Result",
    "Split",
    "compare",
    "derive",
    "emit",
    "holm",
    "load_split",
    "paired_bootstrap",
    "power",
    "report",
    "run",
    "tost",
]

__getattr__ = lazy_aliases(
    __name__,
    {
        "Decoupage": Alias(Split, "archlux.bench.Split"),
        "ModeleTrace": Alias(ModelTrace, "archlux.bench.ModelTrace"),
        "Intervalle": Alias(Interval, "archlux.bench.Interval"),
        "LigneBrute": Alias(RawRow, "archlux.bench.RawRow"),
        "RapportBanc": Alias(BenchReport, "archlux.bench.BenchReport"),
        "Resultat": Alias(Result, "archlux.bench.Result"),
        "StrateOrientation": Alias(OrientationStratum, "archlux.bench.OrientationStratum"),
        "bootstrap_apparie": Alias(paired_bootstrap, "archlux.bench.paired_bootstrap"),
        "charger_decoupage": Alias(load_split, "archlux.bench.load_split"),
        "deriver": Alias(derive, "archlux.bench.derive"),
        "emettre": Alias(emit, "archlux.bench.emit"),
        "puissance": Alias(power, "archlux.bench.power"),
    },
)
