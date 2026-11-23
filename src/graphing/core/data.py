# SPDX-License-Identifier: GPL-3.0-or-later
"""Immutable x–y data: curves and sticks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray

from graphing.core.errors import InvalidData, InvalidUnit
from graphing.core.units import (
    X_QUANTITIES,
    Quantity,
    Unit,
    unit_belongs_to,
)


@dataclass(frozen=True, eq=False)
class _XYData:
    """Common fields and validation. Use a subclass, never this class directly.

    The constructor copies ``x`` and ``y`` once and stores them read-only.

    Raises
    ------
    InvalidData
        Shapes differ, too few points, non-finite values, x not strictly ascending,
        or a quantity used on the wrong axis.
    InvalidUnit
        A unit does not belong to its quantity.
    """

    x: NDArray[np.float64]
    y: NDArray[np.float64]
    x_quantity: Quantity
    x_unit: Unit
    y_quantity: Quantity
    y_unit: Unit

    min_points: ClassVar[int] = 1
    ascending_x: ClassVar[bool] = True

    def __post_init__(self) -> None:
        x = np.array(self.x, dtype=np.float64)
        y = np.array(self.y, dtype=np.float64)
        if x.ndim != 1 or y.ndim != 1:
            raise InvalidData("x and y must be one-dimensional")
        if x.shape != y.shape:
            raise InvalidData(f"x has {x.size} values but y has {y.size}")
        if x.size < self.min_points:
            raise InvalidData(
                f"{type(self).__name__} needs at least {self.min_points} point(s); "
                f"got {x.size}"
            )
        for name, arr in (("x", x), ("y", y)):
            bad = np.flatnonzero(~np.isfinite(arr))
            if bad.size:
                raise InvalidData(f"{name} has a non-finite value at index {bad[0]}")
        if self.ascending_x:
            steps = np.flatnonzero(np.diff(x) <= 0)
            if steps.size:
                raise InvalidData(
                    f"x must be strictly ascending; it is not at index {steps[0] + 1}"
                )
        if self.x_quantity not in X_QUANTITIES:
            raise InvalidData(f"{self.x_quantity.value} cannot be an x quantity")
        if self.y_quantity in X_QUANTITIES:
            raise InvalidData(f"{self.y_quantity.value} cannot be a y quantity")
        if self.y_quantity is Quantity.NORMALISED_INTENSITY:
            raise InvalidData("stored data cannot have normalised intensity as y")
        for quantity, unit in (
            (self.x_quantity, self.x_unit),
            (self.y_quantity, self.y_unit),
        ):
            if not unit_belongs_to(unit, quantity):
                raise InvalidUnit(
                    f"unit {unit.value} does not belong to {quantity.value}"
                )
        x.flags.writeable = False
        y.flags.writeable = False
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        assert isinstance(other, _XYData)
        return (
            self.x_quantity is other.x_quantity
            and self.x_unit is other.x_unit
            and self.y_quantity is other.y_quantity
            and self.y_unit is other.y_unit
            and np.array_equal(self.x, other.x)
            and np.array_equal(self.y, other.y)
        )

    def __hash__(self) -> int:
        return hash(
            (
                type(self).__name__,
                self.x.tobytes(),
                self.y.tobytes(),
                self.x_quantity,
                self.y_quantity,
            )
        )


class CurveData(_XYData):
    """A continuous curve: at least two points."""

    min_points: ClassVar[int] = 2


@dataclass(frozen=True, eq=False)
class StickData(_XYData):
    """A stick spectrum: one or more lines, each a position and a height.

    Lines are kept exactly as the program printed them (D-20261118-02): any order,
    repeated positions allowed. ``labels`` names each line (mode or state number);
    ``None`` means the lines are numbered 1 to n in file order.

    Raises
    ------
    InvalidData
        ``labels`` does not have one entry per line.
    """

    labels: tuple[str, ...] | None = None

    min_points: ClassVar[int] = 1
    ascending_x: ClassVar[bool] = False

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.labels is not None:
            labels = tuple(str(label) for label in self.labels)
            if len(labels) != self.x.size:
                raise InvalidData(
                    f"{len(labels)} labels for {self.x.size} lines; need one per line"
                )
            object.__setattr__(self, "labels", labels)

    def line_labels(self) -> tuple[str, ...]:
        """Return the label of every line (``1`` to ``n`` when none were given)."""
        if self.labels is not None:
            return self.labels
        return tuple(str(i) for i in range(1, self.x.size + 1))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StickData):
            return NotImplemented
        return super().__eq__(other) and self.labels == other.labels

    def __hash__(self) -> int:
        return hash((super().__hash__(), self.labels))
