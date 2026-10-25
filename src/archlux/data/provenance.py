"""Traceable samples: stable identifiers, splits by source plan, counts after each filter.

Eight orientations of one dwelling, or sixteen corruptions of it, are **one** source
plan, not eight or sixteen. A split drawn on the variants lets the same dwelling reach
both the calibration and the test set, and the measured coverage stops being about
unseen plans. This module makes the source explicit in every identifier, splits on the
source, and refuses a split where a source crosses two sets.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeVar

from archlux.data.dedup import HAUSDORFF_THRESHOLD_M, near_duplicate_pairs
from archlux.errors import InvariantViolation
from archlux.seeds import derive

if TYPE_CHECKING:
    from archlux.types import Plan

__all__ = [
    "SPLIT_NAMES",
    "FilterLog",
    "GroupedSplit",
    "SampleId",
    "check_no_group_leakage",
    "cross_split_near_duplicates",
    "split_by_group",
]

T = TypeVar("T")

SPLIT_NAMES = ("train", "validation", "calibration", "test")
"""The four sets, in order. ``validation`` tunes, ``calibration`` fits ``q_hat`` only."""


@dataclass(frozen=True, slots=True, order=True)
class SampleId:
    """Identifier of one sample, down to the run that produced it.

    Attributes
    ----------
    source : str
        Source plan (dwelling): the **statistical unit** and the split key.
    corruption : str
        Corruption applied (``"none"`` for an intact plan), e.g. ``"retrecir:0.25"``.
    variant : str
        Variant of the corrupted plan (``"none"``, ``"az090"``...).
    run : str
        Run that produced the row (seed, repetition).
    """

    source: str
    corruption: str = "none"
    variant: str = "none"
    run: str = "none"

    @property
    def key(self) -> str:
        """Stable textual key ``source/corruption/variant/run``.

        Returns
        -------
        str
            The four fields joined by ``/``; no field may contain ``/``.
        """
        return "/".join((self.source, self.corruption, self.variant, self.run))

    @classmethod
    def parse(cls, key: str) -> SampleId:
        """Read back a :attr:`key`.

        Parameters
        ----------
        key : str
            ``source/corruption/variant/run``.

        Returns
        -------
        SampleId
            The identifier.

        Raises
        ------
        InvariantViolation
            The key does not have four non-empty fields.
        """
        parts = key.split("/")
        if len(parts) != 4 or not all(parts):
            raise InvariantViolation((f"not a sample key: {key!r}",))
        return cls(*parts)

    def __post_init__(self) -> None:
        """Refuse a field that would make :attr:`key` ambiguous.

        Raises
        ------
        InvariantViolation
            A field is empty or contains ``/``.
        """
        for value in (self.source, self.corruption, self.variant, self.run):
            if not value or "/" in value:
                raise InvariantViolation((f"invalid sample id field: {value!r}",))


@dataclass(frozen=True, slots=True)
class GroupedSplit:
    """Four disjoint sets of source plans, with the seed that drew them.

    Attributes
    ----------
    groups : Mapping[str, tuple[str, ...]]
        Set name -> sorted source identifiers. Keys: :data:`SPLIT_NAMES`.
    seed : int
        Root seed of the draw.
    fractions : tuple of float
        Target fractions, in the order of :data:`SPLIT_NAMES`.
    """

    groups: Mapping[str, tuple[str, ...]]
    seed: int
    fractions: tuple[float, ...]

    def of(self, source: str) -> str:
        """Set that holds ``source``.

        Parameters
        ----------
        source : str
            Source plan identifier.

        Returns
        -------
        str
            One of :data:`SPLIT_NAMES`.

        Raises
        ------
        InvariantViolation
            ``source`` is in no set.
        """
        for name, members in self.groups.items():
            if source in members:
                return name
        raise InvariantViolation((f"source not in the split: {source}",))

    def counts(self) -> dict[str, int]:
        """Number of source plans per set.

        Returns
        -------
        dict of str to int
            Set name -> size.
        """
        return {name: len(members) for name, members in self.groups.items()}


def split_by_group(
    sources: Iterable[str], *, seed: int, fractions: Sequence[float] = (0.4, 0.1, 0.25, 0.25)
) -> GroupedSplit:
    """Assign each **source plan** to one of the four sets, never its variants one by one.

    The order is a hash of ``(seed, source)``, so adding a source never moves another
    one, and the draw replays on any machine.

    Parameters
    ----------
    sources : Iterable[str]
        Source plan identifiers (duplicates are merged).
    seed : int
        Root seed. Mandatory, no default.
    fractions : Sequence[float], optional
        Fractions of ``train``, ``validation``, ``calibration``, ``test``; sum 1.

    Returns
    -------
    GroupedSplit
        The four disjoint sets.

    Raises
    ------
    InvariantViolation
        Not four non-negative fractions summing to 1, or no source.
    """
    if len(fractions) != len(SPLIT_NAMES) or min(fractions) < 0.0:
        raise InvariantViolation(("four non-negative fractions expected",))
    if abs(sum(fractions) - 1.0) > 1e-9:
        raise InvariantViolation((f"fractions sum to {sum(fractions)}, not 1",))
    ordered = sorted(set(sources), key=lambda s: (derive(seed, f"split/{s}"), s))
    if not ordered:
        raise InvariantViolation(("no source to split",))
    bounds = [round(sum(fractions[: i + 1]) * len(ordered)) for i in range(len(fractions))]
    starts = [0, *bounds[:-1]]
    groups = {
        name: tuple(sorted(ordered[a:b]))
        for name, a, b in zip(SPLIT_NAMES, starts, bounds, strict=True)
    }
    return GroupedSplit(groups=groups, seed=seed, fractions=tuple(fractions))


def check_no_group_leakage(assignment: Mapping[str, Iterable[SampleId]]) -> None:
    """Refuse sample sets where one source plan appears in two sets.

    Parameters
    ----------
    assignment : Mapping[str, Iterable[SampleId]]
        Set name -> the samples actually used in that set.

    Raises
    ------
    InvariantViolation
        A source appears in two sets; every offending source is named.
    """
    owner: dict[str, str] = {}
    leaks: list[str] = []
    for name, samples in assignment.items():
        for sample in samples:
            seen = owner.setdefault(sample.source, name)
            if seen != name:
                leaks.append(f"{sample.source} in {seen} and {name}")
    if leaks:
        raise InvariantViolation(tuple(sorted(set(leaks))))


def cross_split_near_duplicates(
    split: GroupedSplit,
    plans: Mapping[str, Plan],
    *,
    threshold: float = HAUSDORFF_THRESHOLD_M,
) -> list[tuple[str, str]]:
    """Pairs of source plans, in **different** sets, closer than ``threshold``.

    Deduplication should run before the split; this is the check that it did. A
    near-duplicate pair inside one set is harmless, across two it is a leak.

    Parameters
    ----------
    split : GroupedSplit
        The split to check.
    plans : Mapping[str, Plan]
        Source identifier -> plan (sources missing here are skipped).
    threshold : float, optional
        Dimension gap in metres, see :func:`archlux.data.dedup.near_duplicate_pairs`.

    Returns
    -------
    list of tuple of (str, str)
        Offending pairs, sorted. Empty when the split is clean.
    """
    items = sorted((s, p) for s, p in plans.items())
    pairs = near_duplicate_pairs(items, threshold=threshold)
    return sorted((a, b) for a, b in pairs if split.of(a) != split.of(b))


@dataclass
class FilterLog:
    """Counts before and after each filter of a pipeline, in the order applied.

    A rate is only as honest as its denominator. Every filter that drops a sample goes
    through :meth:`apply`, so the published table can say how many were read, how many
    were dropped and why, without anyone recounting by hand.

    Attributes
    ----------
    steps : list of tuple of (str, int, int)
        ``(filter name, count before, count after)``.
    """

    steps: list[tuple[str, int, int]] = field(default_factory=list)

    def apply(self, name: str, items: Iterable[T], keep: Callable[[T], bool]) -> list[T]:
        """Filter ``items`` and record the counts.

        Parameters
        ----------
        name : str
            Filter name, as it will appear in the report.
        items : Iterable[T]
            Input samples.
        keep : Callable[[T], bool]
            Predicate: ``True`` keeps the sample.

        Returns
        -------
        list
            The kept samples, in order.
        """
        before = list(items)
        after = [item for item in before if keep(item)]
        self.steps.append((name, len(before), len(after)))
        return after

    def to_markdown(self) -> str:
        """Render the counts as a Markdown table.

        Returns
        -------
        str
            One row per filter: before, after, dropped, share kept.
        """
        lines = ["| filter | before | after | dropped | kept |", "|---|--:|--:|--:|--:|"]
        for name, before, after in self.steps:
            share = f"{100 * after / before:.1f} %" if before else "-"
            lines.append(f"| {name} | {before} | {after} | {before - after} | {share} |")
        return "\n".join(lines) + "\n"
