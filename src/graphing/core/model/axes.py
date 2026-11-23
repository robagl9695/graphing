# SPDX-License-Identifier: GPL-3.0-or-later
"""Axes of a panel and the layer arrangement of a y axis (architecture §4.2, §4.3)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from graphing.core.errors import IncompatibleXQuantity, InvalidUnit, NonPositiveValue
from graphing.core.interval import Interval
from graphing.core.region import check_view_limits
from graphing.core.spectrum import Technique
from graphing.core.transforms import YQuantity
from graphing.core.units import X_QUANTITIES, Quantity, Unit, unit_belongs_to


class Side(Enum):
    """Which y axis of a panel a layer is drawn against."""

    LEFT = "left"
    RIGHT = "right"


class Scale(Enum):
    """Display scale of a y axis. It never changes the values."""

    LINEAR = "linear"
    LOG = "log"


@dataclass(frozen=True)
class LayerArrangement:
    """How the layers of one y side are laid out (architecture §7).

    Parameters
    ----------
    normalised : bool
        Every layer is divided by its own maximum.
    stacked : bool
        Each layer is shifted up from the previous one by a gap.
    gap : float or None
        Gap between stacked layers; ``None`` is the default of §7.

    Raises
    ------
    NonPositiveValue
        ``gap`` is given and is not finite and positive.
    """

    normalised: bool = False
    stacked: bool = False
    gap: float | None = None

    def __post_init__(self) -> None:
        if self.gap is not None:
            object.__setattr__(self, "gap", check_gap(self.gap))


OVERLAP = LayerArrangement()
NORMALISED_OVERLAP = LayerArrangement(normalised=True)
STACKED = LayerArrangement(stacked=True)


def check_gap(gap: float) -> float:
    """Return ``gap`` as a float, or raise if it is not finite and positive."""
    value = float(gap)
    if not (math.isfinite(value) and value > 0):
        raise NonPositiveValue(f"a stack gap must be greater than zero; got {gap!r}")
    return value


def check_x_unit(quantity: Quantity, unit: Unit) -> None:
    """Raise unless ``quantity`` is an x quantity and ``unit`` belongs to it."""
    if quantity not in X_QUANTITIES:
        raise IncompatibleXQuantity(f"{quantity.value} is not an x quantity")
    if not unit_belongs_to(unit, quantity):
        raise InvalidUnit(f"unit {unit.value} does not belong to {quantity.value}")


@dataclass(frozen=True, kw_only=True)
class XAxis:
    """The shared x axis of a panel. Its quantity is set by the first layer."""

    quantity: Quantity
    unit: Unit
    limits: tuple[float, float] | None = None
    inverted: bool = False
    secondary: tuple[Quantity, Unit] | None = None
    breaks: tuple[Interval, ...] = ()
    title: str | None = None

    def __post_init__(self) -> None:
        check_x_unit(self.quantity, self.unit)
        if self.limits is not None:
            object.__setattr__(self, "limits", check_view_limits(*self.limits))
        if self.secondary is not None:
            check_x_unit(*self.secondary)


@dataclass(frozen=True, kw_only=True)
class YAxis:
    """One y axis of a panel.

    ``quantity``, ``unit`` and ``domain`` are derived from the layers on the side and
    kept up to date by the operations; the other fields are the user's choices.
    """

    quantity: YQuantity
    unit: Unit
    domain: Technique | None
    limits: tuple[float, float] | None = None
    inverted: bool = False
    scale: Scale = Scale.LINEAR
    arrangement: LayerArrangement = OVERLAP
    title: str | None = None

    def __post_init__(self) -> None:
        if self.limits is not None:
            object.__setattr__(self, "limits", check_view_limits(*self.limits))
