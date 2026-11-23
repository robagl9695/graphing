# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for core.lineshapes (T3.1)."""

import math
from collections.abc import Callable

import numpy as np
import pytest
from numpy.typing import NDArray

from graphing.core.errors import NonPositiveValue
from graphing.core.lineshapes import gaussian, lorentzian, voigt, voigt_fwhm

Shape = Callable[[NDArray[np.float64]], NDArray[np.float64]]

FWHM = 2.0
HALF_WIDTH = 4000.0  # in units of FWHM-scale; wide enough for Lorentzian tails
STEP = 0.01


def grid() -> NDArray[np.float64]:
    return np.arange(-HALF_WIDTH, HALF_WIDTH + STEP / 2, STEP)


def shapes() -> dict[str, Shape]:
    return {
        "gaussian": lambda x: gaussian(x, 0.0, FWHM),
        "lorentzian": lambda x: lorentzian(x, 0.0, FWHM),
        "voigt": lambda x: voigt(x, 0.0, FWHM, 0.5 * FWHM),
    }


def lorentzian_tail(half_width: float, gamma: float) -> float:
    """Area of a unit Lorentzian outside +-half_width (both tails)."""
    return 1.0 - (2.0 / math.pi) * math.atan(half_width / gamma)


@pytest.mark.parametrize("name", ["gaussian", "lorentzian", "voigt"])
def test_area_is_one(name: str) -> None:
    x = grid()
    area = float(np.trapezoid(shapes()[name](x), x))
    # The Lorentzian part decays as 1/x^2: add its analytic tail beyond the grid.
    gamma = {"gaussian": 0.0, "lorentzian": FWHM / 2, "voigt": FWHM / 4}[name]
    if gamma:
        area += lorentzian_tail(HALF_WIDTH, gamma)
    assert area == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("name", ["gaussian", "lorentzian"])
def test_measured_fwhm_equals_parameter(name: str) -> None:
    x = np.arange(-20.0, 20.0 + STEP / 2, STEP)
    y = shapes()[name](x)
    above = x[y >= y.max() / 2]
    assert above.max() - above.min() == pytest.approx(FWHM, abs=STEP)
    assert x[np.argmax(y)] == pytest.approx(0.0, abs=STEP)


def test_voigt_measured_fwhm_matches_approximation() -> None:
    x = np.arange(-20.0, 20.0 + STEP / 2, STEP)
    y = voigt(x, 0.0, FWHM, 0.5 * FWHM)
    above = x[y >= y.max() / 2]
    measured = above.max() - above.min()
    assert measured == pytest.approx(voigt_fwhm(FWHM, 0.5 * FWHM), abs=STEP)


def test_voigt_tends_to_gaussian() -> None:
    x = np.linspace(-10.0, 10.0, 2001)
    diff = voigt(x, 0.0, FWHM, 1e-6 * FWHM) - gaussian(x, 0.0, FWHM)
    assert np.max(np.abs(diff)) < 1e-4 * gaussian(0.0, 0.0, FWHM)


def test_voigt_tends_to_lorentzian() -> None:
    x = np.linspace(-10.0, 10.0, 2001)
    diff = voigt(x, 0.0, 1e-6 * FWHM, FWHM) - lorentzian(x, 0.0, FWHM)
    assert np.max(np.abs(diff)) < 1e-4 * lorentzian(0.0, 0.0, FWHM)


def test_centre_moves_the_peak() -> None:
    x = np.linspace(0.0, 10.0, 1001)
    for y in (gaussian(x, 7.0, 1.0), lorentzian(x, 7.0, 1.0), voigt(x, 7.0, 1.0, 1.0)):
        assert x[np.argmax(y)] == pytest.approx(7.0, abs=0.01)


def test_scalar_and_list_inputs() -> None:
    assert gaussian(0.0, 0.0, 1.0).shape == ()
    assert lorentzian([0.0, 1.0], 0.0, 1.0).shape == (2,)


@pytest.mark.parametrize("bad", [0.0, -1.0, math.nan, math.inf])
def test_widths_must_be_positive(bad: float) -> None:
    with pytest.raises(NonPositiveValue, match="FWHM"):
        gaussian(0.0, 0.0, bad)
    with pytest.raises(NonPositiveValue, match="FWHM"):
        lorentzian(0.0, 0.0, bad)
    with pytest.raises(NonPositiveValue, match="Gaussian FWHM"):
        voigt(0.0, 0.0, bad, 1.0)
    with pytest.raises(NonPositiveValue, match="Lorentzian FWHM"):
        voigt(0.0, 0.0, 1.0, bad)
    with pytest.raises(NonPositiveValue):
        voigt_fwhm(bad, 1.0)
