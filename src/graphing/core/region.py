# SPDX-License-Identifier: GPL-3.0-or-later
"""Select and crop data by an x interval; validate view limits."""

from __future__ import annotations

import dataclasses
import math
from typing import overload

import numpy as np
from numpy.typing import NDArray

from graphing.core.data import CurveData, StickData
from graphing.core.errors import EmptySelection, InvalidInterval
from graphing.core.interval import Interval
from graphing.core.spectrum import Series, Spectrum
from graphing.core.units import DEFAULT_UNIT

# Converting an end between units can move it by one unit in the last place. The
# interval is widened by this relative amount so a point that sits exactly on an end
# stays inside whichever unit the interval was given in.
BOUNDARY_REL_TOL: float = 1e-12


def select_mask(data: CurveData | StickData, interval: Interval) -> NDArray[np.bool_]:
    """Return which points of ``data`` lie inside ``interval`` (ends inclusive).

    The interval may be given in any x unit; it is converted to the data's unit.
    """
    own = interval.to(DEFAULT_UNIT[data.x_quantity])
    low = own.low * (1.0 - BOUNDARY_REL_TOL)
    high = own.high * (1.0 + BOUNDARY_REL_TOL)
    return np.asarray((data.x >= low) & (data.x <= high))


def _crop_data(
    data: CurveData | StickData, interval: Interval
) -> CurveData | StickData:
    mask = select_mask(data, interval)
    needed = type(data).min_points
    if int(mask.sum()) < needed:
        unit = data.x_unit.value
        raise EmptySelection(
            f"fewer than {needed} point(s) of the data fall inside "
            f"{interval.low:g}–{interval.high:g} {interval.unit.value}; the data spans "
            f"{data.x.min():g}–{data.x.max():g} {unit}"
        )
    if isinstance(data, StickData):
        return StickData(
            x=data.x[mask],
            y=data.y[mask],
            x_quantity=data.x_quantity,
            x_unit=data.x_unit,
            y_quantity=data.y_quantity,
            y_unit=data.y_unit,
            labels=tuple(np.array(data.line_labels(), dtype=object)[mask]),
        )
    return CurveData(
        x=data.x[mask],
        y=data.y[mask],
        x_quantity=data.x_quantity,
        x_unit=data.x_unit,
        y_quantity=data.y_quantity,
        y_unit=data.y_unit,
    )


@overload
def crop(obj: CurveData, interval: Interval) -> CurveData: ...
@overload
def crop(obj: StickData, interval: Interval) -> StickData: ...
@overload
def crop(obj: Spectrum, interval: Interval) -> Spectrum: ...
@overload
def crop(obj: Series, interval: Interval) -> Series: ...
def crop(
    obj: CurveData | StickData | Series, interval: Interval
) -> CurveData | StickData | Series:
    """Return a new object holding only the points inside ``interval``.

    Works on curve data, stick data and series or spectra (which keep their name,
    metadata, technique and origin). The input is never modified.

    Raises
    ------
    EmptySelection
        If fewer points remain than the data type needs (2 for a curve, 1 for sticks).
    """
    if isinstance(obj, Series):
        cropped = _crop_data(obj.data, interval)
        return dataclasses.replace(obj, data=cropped)
    return _crop_data(obj, interval)


def check_view_limits(low: float, high: float) -> tuple[float, float]:
    """Validate the limits of an axis view and return them as floats.

    View limits are display only: they never change the values (architecture §8).
    Inverting an axis is a separate option.

    Raises
    ------
    InvalidInterval
        If an end is not finite or ``low`` is not below ``high``.
    """
    low_f, high_f = float(low), float(high)
    if not (math.isfinite(low_f) and math.isfinite(high_f)):
        raise InvalidInterval(f"view limits must be finite; got {low!r} and {high!r}")
    if not low_f < high_f:
        raise InvalidInterval(f"view low ({low_f:g}) must be below high ({high_f:g})")
    return low_f, high_f
