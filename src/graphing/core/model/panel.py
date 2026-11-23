# SPDX-License-Identifier: GPL-3.0-or-later
"""Layers, panels and insets (architecture §4.1, §4.4, §4.5)."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field

from graphing.core.data import StickData
from graphing.core.errors import InvalidData, MissingBroadening
from graphing.core.interval import Interval
from graphing.core.model.axes import Side, XAxis, YAxis
from graphing.core.model.broadening import Broadening
from graphing.core.model.style import Style
from graphing.core.spectrum import Series
from graphing.core.transforms import YTransform

Placement = tuple[float, float, float, float]


def new_id() -> str:
    """Return a new stable identifier for a container."""
    return uuid.uuid4().hex


@dataclass(eq=False, kw_only=True)
class Layer:
    """One series drawn on a panel, with the parameters applied on render.

    ``source`` is shared, never copied. ``broadening`` is required for stick data and
    not allowed otherwise.

    Raises
    ------
    MissingBroadening
        The source holds sticks and ``broadening`` is ``None``.
    InvalidData
        The source is a curve and a broadening is given, or a transform is not a
        :class:`YTransform`.
    """

    source: Series
    broadening: Broadening | None = None
    crop: Interval | None = None
    y_transforms: tuple[YTransform, ...] = ()
    y_axis_side: Side = Side.LEFT
    stack_gap: float | None = None
    style: Style = field(default_factory=Style)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        check_broadening(self.source, self.broadening)
        self.y_transforms = tuple(self.y_transforms)
        if not all(isinstance(t, YTransform) for t in self.y_transforms):
            raise InvalidData("every y transform must be a YTransform")

    @property
    def is_sticks(self) -> bool:
        """Whether the source holds stick data."""
        return isinstance(self.source.data, StickData)


def check_broadening(source: Series, broadening: Broadening | None) -> None:
    """Raise unless ``broadening`` is given exactly when ``source`` holds sticks."""
    if isinstance(source.data, StickData):
        if broadening is None:
            raise MissingBroadening(
                f"{source.name!r} is a stick spectrum: it needs broadening parameters"
            )
    elif broadening is not None:
        raise InvalidData(
            f"{source.name!r} is a curve: broadening applies only to stick spectra"
        )


def check_placement(placement: Placement) -> Placement:
    """Validate an inset placement ``(x0, y0, width, height)`` in host fractions.

    Raises
    ------
    InvalidData
        A value is not finite, the size is not positive, or the inset leaves the
        host's drawing area.
    """
    if len(placement) != 4:
        raise InvalidData("a placement has four values: x0, y0, width, height")
    x0, y0, width, height = (float(v) for v in placement)
    if not all(math.isfinite(v) for v in (x0, y0, width, height)):
        raise InvalidData(f"placement values must be finite; got {placement!r}")
    if width <= 0 or height <= 0:
        raise InvalidData("an inset needs a positive width and height")
    if x0 < 0 or y0 < 0 or x0 + width > 1 or y0 + height > 1:
        raise InvalidData(
            "an inset must lie inside the host's drawing area (fractions 0 to 1)"
        )
    return (x0, y0, width, height)


@dataclass(frozen=True, kw_only=True)
class ZoomInset:
    """A live view of a region of the host panel. It has no layers of its own."""

    region: Interval
    y_limits: tuple[float, float] | None = None


@dataclass(frozen=True, kw_only=True)
class FreeInset:
    """A full panel drawn inside the host."""

    panel: Panel


@dataclass(eq=False, kw_only=True)
class Inset:
    """A small plot placed inside a panel."""

    placement: Placement
    kind: ZoomInset | FreeInset
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        self.placement = check_placement(self.placement)


@dataclass(eq=False, kw_only=True)
class Panel:
    """One plot: an x axis, one or two y axes, layers and insets.

    A new panel is empty (P1). ``is_inset`` is true while the panel is the content of
    a free inset; such a panel cannot hold insets (N1).
    """

    x_axis: XAxis | None = None
    y_left: YAxis | None = None
    y_right: YAxis | None = None
    layers: list[Layer] = field(default_factory=list)
    insets: list[Inset] = field(default_factory=list)
    title: str | None = None
    legend: bool = True
    is_inset: bool = False
    id: str = field(default_factory=new_id)

    @property
    def is_empty(self) -> bool:
        """Whether the panel has no layers."""
        return not self.layers

    def y_axis(self, side: Side) -> YAxis | None:
        """Return the y axis of ``side``, or ``None`` if that side has none."""
        return self.y_left if side is Side.LEFT else self.y_right
