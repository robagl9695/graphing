# SPDX-License-Identifier: GPL-3.0-or-later
"""Sticks → curve (T3.2, architecture §8 step 3).

Each line becomes a line shape of unit area times its height, and the curve is the sum.
The work is done in the unit of the FWHM (cm⁻¹ or eV), which is linear in energy, so
the width of every line is the same whatever its position. Converting the curve to
another x unit for display is a later step that keeps every x–y pair.

The curve keeps the y quantity of the sticks (oscillator strength or km/mol, D-07);
conversions to absorptivity are T3.4. Before broadening, line positions are corrected
by the scale factor and the shift (T3.3, D-20261122-07).
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray

from graphing.core.data import CurveData, StickData
from graphing.core.errors import InvalidData
from graphing.core.lineshapes import gaussian, lorentzian, voigt, voigt_fwhm
from graphing.core.model.broadening import Broadening, LineShape
from graphing.core.units import DEFAULT_UNIT, Quantity, convert_x

Array = NDArray[np.float64]

# Automatic grid step = profile FWHM / 50 (Rob S016). On a uniform grid this keeps
# the sampled peak height within about 0.03 % of the true maximum for a Gaussian.
STEP_PER_FWHM: float = 50.0

# The automatic grid spans the outermost lines ± this many profile FWHMs (Rob S016).
# A Gaussian loses nothing visible there; a Lorentzian keeps about 94 % of its area
# inside ±5 FWHM, which is a display choice: the curve itself is exact at every point.
RANGE_IN_FWHM: float = 5.0


def broadening_quantity(broadening: Broadening) -> Quantity:
    """Return the x quantity broadening is done in (wavenumber or energy)."""
    for quantity, unit in DEFAULT_UNIT.items():
        if unit is broadening.fwhm_unit:
            return quantity
    raise AssertionError("Broadening guarantees an x unit")  # pragma: no cover


def profile_fwhm(broadening: Broadening) -> float:
    """Return the FWHM of one broadened line, in ``broadening.fwhm_unit``.

    For a Voigt profile this is the approximation of :func:`voigt_fwhm`.
    """
    if broadening.line_shape is LineShape.VOIGT:
        assert broadening.fwhm_lorentzian is not None  # Broadening invariant
        return voigt_fwhm(broadening.fwhm, broadening.fwhm_lorentzian)
    return broadening.fwhm


def profile_peak(broadening: Broadening) -> float:
    """Return the height at its centre of one line of unit area, per ``fwhm_unit``.

    A stick of intensity h shown on an absorptivity axis is h times this times the
    conversion factor: the maximum its band would reach alone (D-20261122-08).
    """
    return float(_shape(np.zeros(1), 0.0, broadening)[0])


def grid_step(broadening: Broadening) -> float:
    """Return the grid spacing in use: ``broadening.step`` or the automatic one."""
    if broadening.step is not None:
        return broadening.step
    return profile_fwhm(broadening) / STEP_PER_FWHM


def auto_grid(positions: ArrayLike, broadening: Broadening) -> Array:
    """Return the automatic x grid for lines at ``positions`` (in ``fwhm_unit``).

    The grid is uniform with spacing :func:`grid_step` and spans the outermost lines
    ± ``RANGE_IN_FWHM`` profile FWHMs. It never reaches zero or below, so it can
    always be converted to wavelength.

    Raises
    ------
    InvalidData
        ``positions`` is empty or holds a value that is not finite and positive.
    """
    x = np.asarray(positions, dtype=np.float64)
    if x.size == 0:
        raise InvalidData("there are no lines to broaden")
    if not np.all(np.isfinite(x) & (x > 0)):
        raise InvalidData("line positions must be finite and greater than zero")
    step = grid_step(broadening)
    margin = RANGE_IN_FWHM * profile_fwhm(broadening)
    low = float(x.min()) - margin
    high = float(x.max()) + margin
    if low <= 0:
        # Move the start up by whole steps so the grid stays on the same lattice.
        low += (math.floor(-low / step) + 1) * step
    count = math.floor((high - low) / step) + 1
    return low + step * np.arange(count, dtype=np.float64)


def broaden_lines(
    positions: ArrayLike, heights: ArrayLike, broadening: Broadening, grid: ArrayLike
) -> Array:
    """Return the broadened curve of the given lines on ``grid``.

    Parameters
    ----------
    positions, heights
        One entry per line, in any order; ``positions`` in ``broadening.fwhm_unit``.
        Repeated positions are allowed and add up.
    broadening
        Shape and widths. ``scale_factor`` and ``shift`` are not applied here; they
        act on the sticks in :func:`broaden` (T3.3).
    grid
        x values in ``broadening.fwhm_unit``.

    Returns
    -------
    ndarray
        y on ``grid``; each line's contribution integrates to its height over all x.

    Raises
    ------
    InvalidData
        ``positions`` and ``heights`` differ in length.
    """
    x = np.asarray(positions, dtype=np.float64)
    h = np.asarray(heights, dtype=np.float64)
    if x.shape != h.shape:
        raise InvalidData(f"{x.size} positions but {h.size} heights")
    g = np.asarray(grid, dtype=np.float64)
    y = np.zeros_like(g)
    for centre, height in zip(x, h, strict=True):
        y += height * _shape(g, float(centre), broadening)
    return y


def _shape(grid: Array, centre: float, broadening: Broadening) -> Array:
    if broadening.line_shape is LineShape.GAUSSIAN:
        return gaussian(grid, centre, broadening.fwhm)
    if broadening.line_shape is LineShape.LORENTZIAN:
        return lorentzian(grid, centre, broadening.fwhm)
    assert broadening.fwhm_lorentzian is not None  # Broadening invariant
    return voigt(grid, centre, broadening.fwhm, broadening.fwhm_lorentzian)


def broaden(
    sticks: StickData, broadening: Broadening, grid: ArrayLike | None = None
) -> CurveData:
    """Return the broadened curve of ``sticks``, in ``broadening.fwhm_unit``.

    Parameters
    ----------
    sticks
        The lines as the program printed them (any x unit), corrected by
        :func:`corrected_sticks`. Lines at or below zero (imaginary frequencies) are
        skipped, see :func:`broadened_lines`.
    broadening
        Shape and widths.
    grid
        x values in ``broadening.fwhm_unit``, strictly ascending; ``None`` uses
        :func:`auto_grid`.

    Returns
    -------
    CurveData
        x in ``broadening.fwhm_unit``; y with the quantity and unit of the sticks.

    Raises
    ------
    InvalidData
        No line lies above zero, or ``grid`` is not valid curve x.
    """
    quantity = broadening_quantity(broadening)
    sticks = corrected_sticks(sticks, broadening)
    usable = broadened_lines(sticks)
    if not usable.any():
        raise InvalidData("no line has a position above zero; nothing to broaden")
    positions = positions_in(sticks, quantity)[usable]
    x = auto_grid(positions, broadening) if grid is None else np.asarray(grid, float)
    y = broaden_lines(positions, sticks.y[usable], broadening, x)
    return CurveData(
        x=x,
        y=y,
        x_quantity=quantity,
        x_unit=broadening.fwhm_unit,
        y_quantity=sticks.y_quantity,
        y_unit=sticks.y_unit,
    )


def corrected_sticks(sticks: StickData, broadening: Broadening) -> StickData:
    """Return ``sticks`` with ``x' = scale_factor * x + shift`` applied (T3.3).

    The correction is done in the broadening unit (cm⁻¹ or eV), which is linear in
    energy, so a UV-Vis stick given in nm is converted first and the result is kept
    in the broadening unit. A line at or below zero (imaginary frequency) is not
    moved; a line whose corrected position is at or below zero is kept here and left
    out later by :func:`broadened_lines`, like any non-positive line.

    With factor 1.0 and shift 0.0 the very same object is returned, so the no-op is
    exact. Heights and labels are untouched.

    Parameters
    ----------
    sticks
        The lines as the program printed them (any x unit).
    broadening
        Supplies ``scale_factor``, ``shift`` and the unit to work in.

    Returns
    -------
    StickData
        ``sticks`` itself, or a copy in the broadening unit with corrected x.
    """
    if broadening.scale_factor == 1.0 and broadening.shift == 0.0:
        return sticks
    quantity = broadening_quantity(broadening)
    x = positions_in(sticks, quantity)
    moved = x > 0
    x[moved] = broadening.scale_factor * x[moved] + broadening.shift
    if not np.all(np.isfinite(x)):
        raise InvalidData("the scale factor and shift give a position that overflows")
    return StickData(
        x=x,
        y=sticks.y,
        x_quantity=quantity,
        x_unit=broadening.fwhm_unit,
        y_quantity=sticks.y_quantity,
        y_unit=sticks.y_unit,
        labels=sticks.labels,
    )


def broadened_lines(sticks: StickData) -> NDArray[np.bool_]:
    """Return which lines are broadened and drawn: those with a position above zero.

    A negative position is an imaginary frequency; the reader records it in the
    metadata, and it has no place on an absorption axis (Rob S016).
    """
    return np.asarray(sticks.x > 0)


def positions_in(sticks: StickData, quantity: Quantity) -> Array:
    """Return the line positions converted to ``quantity``, in the stored order.

    Lines at or below zero are left as they are (they cannot be converted).
    """
    out = np.array(sticks.x, dtype=np.float64)
    if sticks.x_quantity is quantity:
        return out
    usable = np.flatnonzero(out > 0)
    order = np.arange(usable.size, dtype=np.float64)
    converted, index = convert_x(out[usable], order, sticks.x_quantity, quantity)
    out[usable[index.astype(np.intp)]] = converted
    return out


__all__ = [
    "RANGE_IN_FWHM",
    "STEP_PER_FWHM",
    "auto_grid",
    "broaden",
    "broaden_lines",
    "broadened_lines",
    "broadening_quantity",
    "corrected_sticks",
    "grid_step",
    "positions_in",
    "profile_fwhm",
    "profile_peak",
]
