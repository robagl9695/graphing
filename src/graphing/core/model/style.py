# SPDX-License-Identifier: GPL-3.0-or-later
"""How a layer is drawn (architecture §3.7)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

from graphing.core.errors import InvalidData, NonPositiveValue

# Rob's EQ figure palette, in cycling order (CLAUDE.md §7).
PALETTE: tuple[str, ...] = ("#0A5199", "#AA1E1E", "#8753C6", "#BF7B00", "#007D50")

_HEX_COLOUR = re.compile(r"#[0-9A-Fa-f]{6}")


class LineStyle(Enum):
    """Dash pattern of a line."""

    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
    DASH_DOT = "dash-dot"


@dataclass(frozen=True, kw_only=True)
class Style:
    """Display options of one layer.

    ``show_curve`` and ``show_sticks`` matter only for stick layers; at least one of
    them must be true. ``sum_sticks`` (stick layers only) sums lines not resolved at
    the current zoom for drawing; it changes no value (architecture §3.7, §8.1).

    Raises
    ------
    InvalidData
        The colour is not ``#RRGGBB`` or both curve and sticks are hidden.
    NonPositiveValue
        The line width is not finite and positive.
    """

    colour: str = PALETTE[0]
    line_width: float = 1.5
    line_style: LineStyle = LineStyle.SOLID
    label: str | None = None
    visible: bool = True
    show_curve: bool = True
    show_sticks: bool = True
    sum_sticks: bool = True

    def __post_init__(self) -> None:
        if not _HEX_COLOUR.fullmatch(self.colour):
            raise InvalidData(f"colour must be written as #RRGGBB; got {self.colour!r}")
        width = float(self.line_width)
        if not (math.isfinite(width) and width > 0):
            raise NonPositiveValue(
                f"line width must be greater than zero; got {self.line_width!r}"
            )
        object.__setattr__(self, "line_width", width)
        if not (self.show_curve or self.show_sticks):
            raise InvalidData("a stick layer must show its curve, its sticks or both")


def default_style(index: int) -> Style:
    """Return the default style of the ``index``-th layer of a panel."""
    return Style(colour=PALETTE[index % len(PALETTE)])
