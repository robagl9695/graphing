# SPDX-License-Identifier: GPL-3.0-or-later
"""A range on an x axis, in any x unit."""

from __future__ import annotations

import math
from dataclasses import dataclass

from graphing.core.errors import InvalidInterval
from graphing.core.units import (
    DEFAULT_UNIT,
    X_QUANTITIES,
    Quantity,
    Unit,
    convert_x,
    unit_belongs_to,
)

_QUANTITY_OF_UNIT: dict[Unit, Quantity] = {DEFAULT_UNIT[q]: q for q in X_QUANTITIES}


@dataclass(frozen=True)
class Interval:
    """A range ``low < high`` of an x quantity.

    It is a range only: it has no step and is never a list of points. It never
    changes; :meth:`to` returns a new interval.

    Raises
    ------
    InvalidInterval
        If the quantity is not an x quantity, the unit does not belong to it, an end
        is not finite and greater than zero, or ``low`` is not below ``high``.
    """

    low: float
    high: float
    quantity: Quantity
    unit: Unit

    def __post_init__(self) -> None:
        if self.quantity not in X_QUANTITIES:
            raise InvalidInterval(f"{self.quantity.value} is not an x quantity")
        if not unit_belongs_to(self.unit, self.quantity):
            raise InvalidInterval(
                f"unit {self.unit.value} does not belong to {self.quantity.value}"
            )
        low, high = float(self.low), float(self.high)
        for end in (low, high):
            if not (math.isfinite(end) and end > 0):
                raise InvalidInterval(
                    f"the ends of an interval must be finite and greater than zero; "
                    f"got {end!r}"
                )
        if not low < high:
            raise InvalidInterval(f"low ({low:g}) must be below high ({high:g})")
        object.__setattr__(self, "low", low)
        object.__setattr__(self, "high", high)

    def to(self, unit: Unit) -> Interval:
        """Return the same range in another x unit, as a new ascending interval.

        Wavelength is inversely proportional to wavenumber and energy, so converting
        to or from it swaps the ends.
        """
        quantity = _QUANTITY_OF_UNIT.get(unit)
        if quantity is None:
            raise InvalidInterval(f"{unit.value} is not an x unit")
        ends, _ = convert_x([self.low, self.high], [0.0, 0.0], self.quantity, quantity)
        return Interval(float(ends[0]), float(ends[1]), quantity, unit)
