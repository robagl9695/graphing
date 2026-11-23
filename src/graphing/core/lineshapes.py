# SPDX-License-Identifier: GPL-3.0-or-later
"""Line shapes for broadening: Gaussian, Lorentzian and Voigt (T3.1).

Every shape has unit area and its maximum at ``centre``. The widths are full widths
at half maximum (FWHM), in the same unit as ``x``; the functions do not know units.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.special import wofz  # type: ignore[import-untyped]  # no stubs

from graphing.core.errors import NonPositiveValue

# FWHM = 2 sqrt(2 ln 2) sigma for a Gaussian.
_FWHM_PER_SIGMA = 2.0 * math.sqrt(2.0 * math.log(2.0))


def _positive(value: float, what: str) -> float:
    number = float(value)
    if not (math.isfinite(number) and number > 0):
        raise NonPositiveValue(f"{what} must be greater than zero; got {value!r}")
    return number


def gaussian(x: ArrayLike, centre: float, fwhm: float) -> NDArray[np.float64]:
    """Return a Gaussian of unit area.

    Raises
    ------
    NonPositiveValue
        ``fwhm`` is not finite and positive.
    """
    sigma = _positive(fwhm, "the FWHM") / _FWHM_PER_SIGMA
    u = (np.asarray(x, dtype=np.float64) - centre) / sigma
    return np.asarray(np.exp(-0.5 * u * u) / (sigma * math.sqrt(2.0 * math.pi)))


def lorentzian(x: ArrayLike, centre: float, fwhm: float) -> NDArray[np.float64]:
    """Return a Lorentzian of unit area.

    Raises
    ------
    NonPositiveValue
        ``fwhm`` is not finite and positive.
    """
    half = _positive(fwhm, "the FWHM") / 2.0
    d = np.asarray(x, dtype=np.float64) - centre
    return np.asarray(half / (math.pi * (d * d + half * half)))


def voigt(
    x: ArrayLike, centre: float, fwhm_gaussian: float, fwhm_lorentzian: float
) -> NDArray[np.float64]:
    """Return a Voigt profile of unit area: a Gaussian convolved with a Lorentzian.

    Computed exactly from the Faddeeva function.

    Parameters
    ----------
    x, centre
        Positions, in one unit.
    fwhm_gaussian, fwhm_lorentzian
        FWHM of the two components, in the same unit. Both must be above zero; for a
        pure shape use :func:`gaussian` or :func:`lorentzian`.

    Raises
    ------
    NonPositiveValue
        A width is not finite and positive.
    """
    sigma = _positive(fwhm_gaussian, "the Gaussian FWHM") / _FWHM_PER_SIGMA
    gamma = _positive(fwhm_lorentzian, "the Lorentzian FWHM") / 2.0
    z = (np.asarray(x, dtype=np.float64) - centre + 1j * gamma) / (
        sigma * math.sqrt(2.0)
    )
    return np.asarray(wofz(z).real / (sigma * math.sqrt(2.0 * math.pi)))


def voigt_fwhm(fwhm_gaussian: float, fwhm_lorentzian: float) -> float:
    """Return the FWHM of a Voigt profile (approximation, relative error ~0.02 %).

    Source: [olivero1977] (pending verification):
    f_V = 0.5346 f_L + sqrt(0.2166 f_L^2 + f_G^2).

    Raises
    ------
    NonPositiveValue
        A width is not finite and positive.
    """
    f_g = _positive(fwhm_gaussian, "the Gaussian FWHM")
    f_l = _positive(fwhm_lorentzian, "the Lorentzian FWHM")
    return 0.5346 * f_l + math.sqrt(0.2166 * f_l * f_l + f_g * f_g)
