# SPDX-License-Identifier: GPL-3.0-or-later
"""Small spectra shared by the model, operations and evaluation tests."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike

from graphing.core.data import CurveData, StickData
from graphing.core.model import Broadening, LineShape
from graphing.core.spectrum import Origin, Spectrum, Technique
from graphing.core.units import DEFAULT_UNIT, Quantity, Unit

NM = Quantity.WAVELENGTH
CM1 = Quantity.WAVENUMBER
ABS = Quantity.ABSORBANCE


def curve(
    x: ArrayLike,
    y: ArrayLike,
    *,
    x_quantity: Quantity = NM,
    y_quantity: Quantity = ABS,
    technique: Technique = Technique.UV_VIS,
    name: str = "curve",
) -> Spectrum:
    """Return an experimental spectrum holding a curve."""
    data = CurveData(
        x=np.asarray(x, dtype=float),
        y=np.asarray(y, dtype=float),
        x_quantity=x_quantity,
        x_unit=DEFAULT_UNIT[x_quantity],
        y_quantity=y_quantity,
        y_unit=DEFAULT_UNIT[y_quantity],
    )
    return Spectrum(
        name=name, data=data, technique=technique, origin=Origin.EXPERIMENTAL
    )


def uv_abs(name: str = "uv", scale: float = 1.0) -> Spectrum:
    """UV-Vis absorbance, 300–600 nm, one band with maximum ``scale`` at 450 nm."""
    x = np.linspace(300.0, 600.0, 301)
    return curve(x, scale * np.exp(-(((x - 450.0) / 40.0) ** 2)), name=name)


def ir_abs(name: str = "ir", scale: float = 1.0) -> Spectrum:
    """IR absorbance, 500–4000 cm⁻¹, one band with maximum ``scale`` at 1700 cm⁻¹."""
    x = np.linspace(500.0, 4000.0, 351)
    y = scale * np.exp(-(((x - 1700.0) / 50.0) ** 2))
    return curve(x, y, x_quantity=CM1, technique=Technique.IR, name=name)


def uv_sticks(name: str = "uv_th") -> Spectrum:
    """Theoretical UV-Vis sticks in eV with oscillator strengths."""
    data = StickData(
        x=np.array([2.5, 3.1, 4.0]),
        y=np.array([0.1, 0.4, 0.2]),
        x_quantity=Quantity.ENERGY,
        x_unit=Unit.EV,
        y_quantity=Quantity.OSCILLATOR_STRENGTH,
        y_unit=Unit.DIMENSIONLESS,
    )
    return Spectrum(
        name=name, data=data, technique=Technique.UV_VIS, origin=Origin.THEORETICAL
    )


GAUSS_03_EV = Broadening(line_shape=LineShape.GAUSSIAN, fwhm=0.3, fwhm_unit=Unit.EV)
