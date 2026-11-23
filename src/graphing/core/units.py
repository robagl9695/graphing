# SPDX-License-Identifier: GPL-3.0-or-later
"""X-axis quantities, units and conversions between them."""

from __future__ import annotations

from enum import Enum

import numpy as np
from numpy.typing import ArrayLike, NDArray

from graphing.core import constants
from graphing.core.errors import IncompatibleXQuantity, NonPositiveValue


class Quantity(Enum):
    """What an axis measures. WAVELENGTH, WAVENUMBER and ENERGY are x quantities."""

    WAVELENGTH = "wavelength"
    WAVENUMBER = "wavenumber"
    ENERGY = "energy"
    ABSORBANCE = "absorbance"
    TRANSMITTANCE = "transmittance"
    MOLAR_ABSORPTIVITY = "molar absorptivity"
    INTENSITY = "intensity"
    OSCILLATOR_STRENGTH = "oscillator strength"
    IR_INTENSITY = "IR intensity"
    # Result of normalisation only; never the y quantity of stored data.
    NORMALISED_INTENSITY = "normalised intensity"


class Unit(Enum):
    """How a quantity is expressed."""

    NM = "nm"
    CM1 = "cm⁻¹"
    EV = "eV"
    PERCENT = "%"
    L_MOL_CM = "L mol⁻¹ cm⁻¹"
    KM_MOL = "km mol⁻¹"
    ARBITRARY = "arbitrary"
    DIMENSIONLESS = "—"


# Each quantity has exactly one unit in v1.0.
DEFAULT_UNIT: dict[Quantity, Unit] = {
    Quantity.WAVELENGTH: Unit.NM,
    Quantity.WAVENUMBER: Unit.CM1,
    Quantity.ENERGY: Unit.EV,
    Quantity.ABSORBANCE: Unit.DIMENSIONLESS,
    Quantity.TRANSMITTANCE: Unit.PERCENT,
    Quantity.MOLAR_ABSORPTIVITY: Unit.L_MOL_CM,
    Quantity.INTENSITY: Unit.ARBITRARY,
    Quantity.OSCILLATOR_STRENGTH: Unit.DIMENSIONLESS,
    Quantity.IR_INTENSITY: Unit.KM_MOL,
    Quantity.NORMALISED_INTENSITY: Unit.DIMENSIONLESS,
}

X_QUANTITIES: frozenset[Quantity] = frozenset(
    {Quantity.WAVELENGTH, Quantity.WAVENUMBER, Quantity.ENERGY}
)


def unit_belongs_to(unit: Unit, quantity: Quantity) -> bool:
    """Return whether ``unit`` is a valid unit of ``quantity``."""
    return DEFAULT_UNIT[quantity] is unit


def _to_ev(x: NDArray[np.float64], quantity: Quantity) -> NDArray[np.float64]:
    if quantity is Quantity.WAVELENGTH:
        return constants.HC_EV_NM / x
    if quantity is Quantity.WAVENUMBER:
        return x / constants.EV_TO_CM1
    return x.copy()


def _from_ev(e: NDArray[np.float64], quantity: Quantity) -> NDArray[np.float64]:
    if quantity is Quantity.WAVELENGTH:
        return constants.HC_EV_NM / e
    if quantity is Quantity.WAVENUMBER:
        return e * constants.EV_TO_CM1
    return e.copy()


def convert_x(
    x: ArrayLike,
    y: ArrayLike,
    from_quantity: Quantity,
    to_quantity: Quantity,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Convert x between wavelength, wavenumber and energy, keeping x–y pairs.

    Parameters
    ----------
    x : array_like
        Values in the default unit of ``from_quantity`` (nm, cm⁻¹ or eV).
    y : array_like
        Values paired with ``x``; same length. Reordered together with ``x``.
    from_quantity, to_quantity : Quantity
        Source and target quantities.

    Returns
    -------
    x_new, y_new : ndarray
        New arrays (the inputs are not modified), with ``x_new`` ascending.

    Raises
    ------
    NonPositiveValue
        If any x is not finite and strictly positive.
    IncompatibleXQuantity
        If the arguments are not ``Quantity`` members.
    ValueError
        If ``x`` and ``y`` differ in shape.
    """
    for q in (from_quantity, to_quantity):
        if not isinstance(q, Quantity):
            raise IncompatibleXQuantity(f"{q!r} is not an x quantity")
    x_arr = np.array(x, dtype=np.float64)
    y_arr = np.array(y, dtype=np.float64)
    if x_arr.shape != y_arr.shape:
        raise ValueError(f"x and y differ in shape: {x_arr.shape} vs {y_arr.shape}")
    bad = ~(np.isfinite(x_arr) & (x_arr > 0))
    if bad.any():
        first = x_arr[bad].flat[0]
        raise NonPositiveValue(
            f"x values must be finite and greater than zero; found {first!r} "
            f"({int(bad.sum())} invalid value(s))"
        )
    if from_quantity is to_quantity:
        x_new = x_arr
    else:
        x_new = _from_ev(_to_ev(x_arr, from_quantity), to_quantity)
    order = np.argsort(x_new, kind="stable")
    return x_new[order], y_arr[order]
