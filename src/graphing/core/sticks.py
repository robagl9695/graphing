# SPDX-License-Identifier: GPL-3.0-or-later
"""Grouping of stick lines for display (architecture §8.1, D-20261118-02 to -05).

Pure functions: grouping never changes the stored lines, only what is drawn.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from graphing.core.errors import InvalidData, NonPositiveValue


@dataclass(frozen=True)
class StickGroup:
    """One drawn stick: one line or several lines summed.

    Attributes
    ----------
    position
        Where it is drawn, in the x unit given to :func:`group_sticks`.
    height
        Sum of the members' heights.
    members
        ``line_index`` values of the lines it stands for, ascending (file order).
    degenerate
        Several members share exactly one position.
    unresolved
        Members at different positions were summed because they are not resolved.
    """

    position: float
    height: float
    members: tuple[int, ...]
    degenerate: bool
    unresolved: bool

    @property
    def is_summed(self) -> bool:
        """Whether the stick stands for more than one line."""
        return len(self.members) > 1


def group_sticks(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    line_index: NDArray[np.intp],
    resolution: float,
    sum_unresolved: bool = True,
) -> list[StickGroup]:
    """Group stick lines for drawing, ordered by position.

    Lines at exactly the same position are always summed. If ``sum_unresolved``,
    lines closer than ``resolution`` are summed too: sorted by position, a group
    starts at the lowest line not yet grouped and takes every line within
    ``resolution`` of it (anchored, no chaining, stable under panning). A group of
    different positions is drawn at the intensity-weighted centroid; if the sum is 0,
    at the tallest member (ties: first in file order).

    Parameters
    ----------
    x, y, line_index
        Position, height and source line number of each line.
    resolution
        Width in x units below which lines are not resolved on the figure.
    sum_unresolved
        Also sum lines that are not resolved (``Style.sum_sticks``).

    Raises
    ------
    InvalidData
        The arrays differ in length.
    NonPositiveValue
        ``resolution`` is not finite and positive.
    """
    if not (x.shape == y.shape == line_index.shape):
        raise InvalidData("x, y and line_index must have the same length")
    if not (math.isfinite(resolution) and resolution > 0):
        raise NonPositiveValue(f"resolution must be above zero; got {resolution!r}")
    order = np.argsort(x, kind="stable")
    xs, ys, idx = x[order], y[order], line_index[order]
    groups: list[StickGroup] = []
    n = xs.size
    start = 0
    while start < n:
        anchor = xs[start]
        end = start + 1
        while end < n and (
            xs[end] - anchor < resolution if sum_unresolved else xs[end] == anchor
        ):
            end += 1
        groups.append(_make_group(xs[start:end], ys[start:end], idx[start:end]))
        start = end
    return groups


def _make_group(
    x: NDArray[np.float64], y: NDArray[np.float64], idx: NDArray[np.intp]
) -> StickGroup:
    total = float(y.sum())
    same_position = bool(np.all(x == x[0]))
    if same_position:
        position = float(x[0])
    elif total != 0.0:
        position = float(np.dot(x, y) / total)
    else:
        tallest = np.flatnonzero(y == y.max())
        position = float(x[tallest[np.argmin(idx[tallest])]])
    return StickGroup(
        position=position,
        height=total,
        members=tuple(int(i) for i in np.sort(idx)),
        degenerate=same_position and x.size > 1,
        unresolved=not same_position,
    )
