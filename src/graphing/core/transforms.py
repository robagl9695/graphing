# SPDX-License-Identifier: GPL-3.0-or-later
"""Y transforms: parameter objects applied on demand to the raw data.

A transform never changes its input and nothing derived is stored. A layer keeps a
tuple of transforms and :func:`apply_transforms` recomputes the result from the raw
arrays every time, so removing a transform from the tuple restores the previous curve.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray

from graphing.core.constants import (
    EV_TO_CM1,
    INTEGRATED_ABSORPTIVITY_PER_F,
    INTEGRATED_ABSORPTIVITY_PER_KM_MOL,
)
from graphing.core.errors import (
    CannotNormalise,
    DivisionByZero,
    InvalidTransform,
    NonPositiveValue,
)
from graphing.core.units import X_QUANTITIES, Quantity, Unit, convert_x, unit_belongs_to

Array = NDArray[np.float64]


@dataclass(frozen=True)
class DerivedQuantity:
    """A y quantity produced by a transform that has no standard name.

    Two derived quantities are equal only when they come from the same operation on
    the same source, which is what decides whether two layers can share a y axis.
    """

    operation: str
    source: Quantity | DerivedQuantity


YQuantity = Quantity | DerivedQuantity


def _require_positive(y: Array, what: str) -> None:
    bad = np.flatnonzero(~(y > 0))
    if bad.size:
        raise NonPositiveValue(
            f"{what} needs values greater than zero; found {y[bad[0]]!r} "
            f"at index {bad[0]}"
        )


def _require_finite(y: Array, what: str) -> Array:
    if not np.all(np.isfinite(y)):
        raise InvalidTransform(f"{what} gives a value that is not finite")
    return y


@dataclass(frozen=True)
class YTransform:
    """Base class. Subclasses define ``label``, ``result_quantity`` and ``apply``."""

    label: ClassVar[str] = ""

    def result_quantity(self, y_quantity: YQuantity) -> YQuantity:
        """Return the y quantity after the transform, or raise if it cannot apply."""
        return y_quantity

    def apply(self, x: Array, y: Array, x_quantity: Quantity) -> Array:
        """Return the transformed y as a new array.

        Parameters
        ----------
        x : ndarray
            Strictly ascending x values, in the default unit of ``x_quantity``.
        y : ndarray
            Values paired with ``x``.
        x_quantity : Quantity
            What ``x`` measures.
        """
        raise NotImplementedError


@dataclass(frozen=True)
class TransmittanceToAbsorbance(YTransform):
    """A = 2 - log10(%T)."""

    label: ClassVar[str] = "%T → A"

    def result_quantity(self, y_quantity: YQuantity) -> YQuantity:
        if y_quantity is not Quantity.TRANSMITTANCE:
            raise InvalidTransform("%T → A needs a transmittance y axis")
        return Quantity.ABSORBANCE

    def apply(self, x: Array, y: Array, x_quantity: Quantity) -> Array:
        _require_positive(y, "%T → A")
        return 2.0 - np.log10(y)


@dataclass(frozen=True)
class AbsorbanceToTransmittance(YTransform):
    """%T = 10 ** (2 - A)."""

    label: ClassVar[str] = "A → %T"

    def result_quantity(self, y_quantity: YQuantity) -> YQuantity:
        if y_quantity is not Quantity.ABSORBANCE:
            raise InvalidTransform("A → %T needs an absorbance y axis")
        return Quantity.TRANSMITTANCE

    def apply(self, x: Array, y: Array, x_quantity: Quantity) -> Array:
        with np.errstate(over="ignore"):
            return _require_finite(10.0 ** (2.0 - y), "A → %T")


@dataclass(frozen=True)
class Log10(YTransform):
    """Base-10 logarithm of y."""

    label: ClassVar[str] = "log10"

    def result_quantity(self, y_quantity: YQuantity) -> YQuantity:
        return DerivedQuantity("log10", y_quantity)

    def apply(self, x: Array, y: Array, x_quantity: Quantity) -> Array:
        _require_positive(y, "log10")
        return np.log10(y)


@dataclass(frozen=True)
class Inverse(YTransform):
    """1 / y."""

    label: ClassVar[str] = "1/y"

    def result_quantity(self, y_quantity: YQuantity) -> YQuantity:
        return DerivedQuantity("inverse", y_quantity)

    def apply(self, x: Array, y: Array, x_quantity: Quantity) -> Array:
        zero = np.flatnonzero(y == 0)
        if zero.size:
            raise DivisionByZero(f"1/y found y = 0 at index {zero[0]}")
        with np.errstate(over="ignore"):
            return _require_finite(1.0 / y, "1/y")


@dataclass(frozen=True)
class Level(YTransform):
    """Subtract a constant from y (constant levelling; no baseline fitting)."""

    constant: float
    label: ClassVar[str] = "level"

    def __post_init__(self) -> None:
        if not math.isfinite(self.constant):
            raise InvalidTransform(
                f"the level constant must be finite; got {self.constant!r}"
            )

    def apply(self, x: Array, y: Array, x_quantity: Quantity) -> Array:
        return y - self.constant


@dataclass(frozen=True)
class NormaliseToMax(YTransform):
    """Divide y by its maximum, so the highest point is exactly 1."""

    label: ClassVar[str] = "normalise to maximum"

    def result_quantity(self, y_quantity: YQuantity) -> YQuantity:
        return Quantity.NORMALISED_INTENSITY

    def apply(self, x: Array, y: Array, x_quantity: Quantity) -> Array:
        top = y.max()
        if not top > 0:
            raise CannotNormalise(
                f"the maximum of y is {top!r}; it must be greater than zero"
            )
        return y / top


@dataclass(frozen=True)
class NormaliseAtX(YTransform):
    """Divide y by its value at a chosen x (linear interpolation)."""

    x: float
    quantity: Quantity
    unit: Unit
    label: ClassVar[str] = "normalise at x"

    def __post_init__(self) -> None:
        if self.quantity not in X_QUANTITIES or not unit_belongs_to(
            self.unit, self.quantity
        ):
            raise InvalidTransform(
                "the reference x needs an x quantity with its own unit"
            )
        if not (math.isfinite(self.x) and self.x > 0):
            raise NonPositiveValue(
                f"the reference x must be greater than zero; got {self.x!r}"
            )

    def result_quantity(self, y_quantity: YQuantity) -> YQuantity:
        return Quantity.NORMALISED_INTENSITY

    def apply(self, x: Array, y: Array, x_quantity: Quantity) -> Array:
        if self.quantity is x_quantity:
            x0 = self.x
        else:
            x0 = float(convert_x([self.x], [0.0], self.quantity, x_quantity)[0][0])
        if not x[0] <= x0 <= x[-1]:
            raise CannotNormalise(
                f"the reference x ({x0:g}) is outside the data range "
                f"[{x[0]:g}, {x[-1]:g}]"
            )
        reference = float(np.interp(x0, x, y))
        if reference == 0.0:
            raise CannotNormalise("the value of y at the reference x is zero")
        return y / reference


@dataclass(frozen=True)
class LinesToAbsorptivity(YTransform):
    """Base of the two conversions of line intensities to molar absorptivity (T3.4).

    The y of a broadened curve is a density: line intensity per unit of the x it was
    broadened in. The conversion multiplies it by the integrated molar absorptivity of
    one unit of intensity (``per_unit_intensity``, L mol⁻¹ cm⁻²) and, when x is an
    energy in eV, divides by the cm⁻¹ in one eV, because ε is per cm⁻¹. A density
    per nm is not defined here (broadening is never done in nm, T3.2).

    It is linear, so it can act on the lines before broadening (D-20261122-08). A
    stick shown on an ε axis is the ε maximum of its band alone; that step needs the
    line shape and is done in ``core.evaluate``.
    """

    source: ClassVar[Quantity]
    per_unit_intensity: ClassVar[float]

    def result_quantity(self, y_quantity: YQuantity) -> YQuantity:
        if y_quantity is not self.source:
            raise InvalidTransform(f"{self.label} needs a {self.source.value} y axis")
        return Quantity.MOLAR_ABSORPTIVITY

    def factor(self, x_quantity: Quantity) -> float:
        """Return what a density per unit of ``x_quantity`` is multiplied by.

        Raises
        ------
        InvalidTransform
            ``x_quantity`` is not wavenumber or energy.
        """
        if x_quantity is Quantity.WAVENUMBER:
            return self.per_unit_intensity
        if x_quantity is Quantity.ENERGY:
            return self.per_unit_intensity / EV_TO_CM1
        raise InvalidTransform(
            f"{self.label} needs the curve as a density per cm⁻¹ or per eV; "
            f"it is per {x_quantity.value}"
        )

    def apply(self, x: Array, y: Array, x_quantity: Quantity) -> Array:
        """Return ε for ``y`` given as a density per unit of ``x_quantity``."""
        return y * self.factor(x_quantity)


@dataclass(frozen=True)
class OscillatorStrengthToAbsorptivity(LinesToAbsorptivity):
    """f → ε: ∫ε dν̃ = INTEGRATED_ABSORPTIVITY_PER_F · f (docs/theory.md §1)."""

    label: ClassVar[str] = "f → ε"
    source: ClassVar[Quantity] = Quantity.OSCILLATOR_STRENGTH
    per_unit_intensity: ClassVar[float] = INTEGRATED_ABSORPTIVITY_PER_F


@dataclass(frozen=True)
class IRIntensityToAbsorptivity(LinesToAbsorptivity):
    """km/mol → ε: ∫ε dν̃ = (100 / ln 10) · A (docs/theory.md §2, D-20261117-01)."""

    label: ClassVar[str] = "km/mol → ε"
    source: ClassVar[Quantity] = Quantity.IR_INTENSITY
    per_unit_intensity: ClassVar[float] = INTEGRATED_ABSORPTIVITY_PER_KM_MOL


def _beer_lambert_product(path_length_cm: float, concentration_mol_l: float) -> float:
    for value, what in (
        (path_length_cm, "path length"),
        (concentration_mol_l, "concentration"),
    ):
        if not (math.isfinite(value) and value > 0):
            raise NonPositiveValue(
                f"the {what} must be a finite number greater than zero; got {value!r}"
            )
    return path_length_cm * concentration_mol_l


@dataclass(frozen=True)
class AbsorptivityToAbsorbance(YTransform):
    """Beer–Lambert: A = ε · b · c, with b in cm and c in mol/L (docs/theory.md §3)."""

    path_length_cm: float
    concentration_mol_l: float
    label: ClassVar[str] = "ε → A"

    def __post_init__(self) -> None:
        _beer_lambert_product(self.path_length_cm, self.concentration_mol_l)

    def result_quantity(self, y_quantity: YQuantity) -> YQuantity:
        if y_quantity is not Quantity.MOLAR_ABSORPTIVITY:
            raise InvalidTransform("ε → A needs a molar absorptivity y axis")
        return Quantity.ABSORBANCE

    def apply(self, x: Array, y: Array, x_quantity: Quantity) -> Array:
        return y * (self.path_length_cm * self.concentration_mol_l)


@dataclass(frozen=True)
class AbsorbanceToAbsorptivity(YTransform):
    """Beer–Lambert: ε = A / (b · c), with b in cm and c in mol/L."""

    path_length_cm: float
    concentration_mol_l: float
    label: ClassVar[str] = "A → ε"

    def __post_init__(self) -> None:
        _beer_lambert_product(self.path_length_cm, self.concentration_mol_l)

    def result_quantity(self, y_quantity: YQuantity) -> YQuantity:
        if y_quantity is not Quantity.ABSORBANCE:
            raise InvalidTransform("A → ε needs an absorbance y axis")
        return Quantity.MOLAR_ABSORPTIVITY

    def apply(self, x: Array, y: Array, x_quantity: Quantity) -> Array:
        return y / (self.path_length_cm * self.concentration_mol_l)


def apply_transforms(
    x: Array,
    y: Array,
    x_quantity: Quantity,
    y_quantity: YQuantity,
    transforms: Sequence[YTransform],
) -> tuple[Array, YQuantity]:
    """Apply ``transforms`` in order to the raw ``y``.

    Returns
    -------
    y_new, effective_quantity
        A new array and the y quantity after all the transforms. The inputs are not
        modified.

    Raises
    ------
    InvalidTransform
        A transform does not fit the y quantity at its step, or gives non-finite values.
    NonPositiveValue, DivisionByZero, CannotNormalise
        The values are outside what a transform accepts.
    """
    result = np.array(y, dtype=np.float64)
    quantity = y_quantity
    for transform in transforms:
        next_quantity = transform.result_quantity(quantity)
        result = transform.apply(x, result, x_quantity)
        quantity = next_quantity
    return result, quantity
