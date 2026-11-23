# SPDX-License-Identifier: GPL-3.0-or-later
"""Broadening parameters of a stick layer (architecture §3.4).

Only the parameters live here. Turning sticks into a curve is ``core.broadening``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from graphing.core.errors import InvalidData, InvalidUnit, NonPositiveValue
from graphing.core.units import Unit

# Broadening is done in a variable linear in energy (T3.2, Rob S016: a FWHM in nm is
# not accepted, because a constant width in nm is not a constant width in energy).
BROADENING_UNITS: frozenset[Unit] = frozenset({Unit.CM1, Unit.EV})


class LineShape(Enum):
    """Shape of each broadened line."""

    GAUSSIAN = "Gaussian"
    LORENTZIAN = "Lorentzian"
    VOIGT = "Voigt"


def _require_positive(value: float, what: str) -> float:
    number = float(value)
    if not (math.isfinite(number) and number > 0):
        raise NonPositiveValue(f"{what} must be greater than zero; got {value!r}")
    return number


@dataclass(frozen=True, kw_only=True)
class Broadening:
    """How the sticks of a theoretical spectrum are turned into a curve.

    Parameters
    ----------
    line_shape : LineShape
    fwhm : float
        Full width at half maximum, > 0, in ``fwhm_unit``. For a Voigt profile it is
        the width of the Gaussian component (option A, Rob S015).
    fwhm_unit : Unit
        cm⁻¹ or eV: broadening is done in a variable linear in energy.
    scale_factor : float
        Multiplies the line positions, > 0. 1.0 leaves them where they are. In IR it
        is the usual frequency scale factor ([scott1996], [merrick2007]); in UV-Vis
        it is a calibration the user chooses (T3.3).
    shift : float
        Added to the line positions after scaling, in ``fwhm_unit``; any finite value,
        0.0 leaves them where they are (T3.3).
    step : float or None
        Spacing of the computed grid in ``fwhm_unit``, > 0; ``None`` is automatic.
    fwhm_lorentzian : float or None
        Width of the Lorentzian component of a Voigt profile, > 0, in ``fwhm_unit``.
        Required for Voigt; must be ``None`` for the other shapes.

    Raises
    ------
    NonPositiveValue
        ``fwhm``, ``scale_factor``, ``step`` or ``fwhm_lorentzian`` is not finite and
        positive.
    InvalidData
        ``shift`` is not finite.
    InvalidUnit
        ``fwhm_unit`` is not cm⁻¹ or eV.
    InvalidData
        A Voigt profile without ``fwhm_lorentzian``, or another shape with one.
    """

    line_shape: LineShape
    fwhm: float
    fwhm_unit: Unit
    scale_factor: float = 1.0
    shift: float = 0.0
    step: float | None = None
    fwhm_lorentzian: float | None = None

    def __post_init__(self) -> None:
        if self.fwhm_unit not in BROADENING_UNITS:
            raise InvalidUnit(
                f"the FWHM must be in cm-1 or eV (broadening is linear in energy); "
                f"got {self.fwhm_unit.value}"
            )
        object.__setattr__(self, "fwhm", _require_positive(self.fwhm, "the FWHM"))
        object.__setattr__(
            self,
            "scale_factor",
            _require_positive(self.scale_factor, "the scale factor"),
        )
        shift = float(self.shift)
        if not math.isfinite(shift):
            raise InvalidData(f"the shift must be a finite number; got {self.shift!r}")
        object.__setattr__(self, "shift", shift)
        if self.step is not None:
            object.__setattr__(
                self, "step", _require_positive(self.step, "the grid step")
            )
        if self.line_shape is LineShape.VOIGT:
            if self.fwhm_lorentzian is None:
                raise InvalidData("a Voigt profile needs the Lorentzian FWHM")
            object.__setattr__(
                self,
                "fwhm_lorentzian",
                _require_positive(self.fwhm_lorentzian, "the Lorentzian FWHM"),
            )
        elif self.fwhm_lorentzian is not None:
            raise InvalidData(
                f"a Lorentzian FWHM applies only to a Voigt profile, "
                f"not to a {self.line_shape.value} one"
            )
