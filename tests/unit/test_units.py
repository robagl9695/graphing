# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for core.units and core.constants (T1.2)."""

import itertools

import numpy as np
import pytest

from graphing.core import constants
from graphing.core.errors import GraphingError, IncompatibleXQuantity, NonPositiveValue
from graphing.core.units import Quantity, convert_x

W, N, E = Quantity.WAVELENGTH, Quantity.WAVENUMBER, Quantity.ENERGY
REF = {W: 500.0, N: 20000.0, E: 2.479684}
PAIRS = list(itertools.permutations([W, N, E], 2))


@pytest.mark.parametrize(("src", "dst"), PAIRS)
def test_reference_value(src: Quantity, dst: Quantity) -> None:
    x, _ = convert_x([REF[src]], [1.0], src, dst)
    assert x[0] == pytest.approx(REF[dst], rel=1e-6)


@pytest.mark.parametrize(("src", "dst"), PAIRS)
def test_round_trip(src: Quantity, dst: Quantity) -> None:
    rng = np.random.default_rng(1)
    x = np.sort(rng.uniform(1.0, 5000.0, 200))
    y = rng.normal(size=200)
    xa, ya = convert_x(x, y, src, dst)
    xb, yb = convert_x(xa, ya, dst, src)
    np.testing.assert_allclose(xb, x, rtol=1e-12)
    np.testing.assert_array_equal(yb, y)


def test_pairing_and_ascending() -> None:
    x = np.array([200.0, 400.0, 800.0])
    y = np.array([1.0, 2.0, 3.0])
    xn, yn = convert_x(x, y, W, N)
    assert np.all(np.diff(xn) > 0)
    np.testing.assert_array_equal(yn, [3.0, 2.0, 1.0])
    np.testing.assert_allclose(xn, 1e7 / x[::-1], rtol=1e-12)


def test_order_kept_between_wavenumber_and_energy() -> None:
    _, y = convert_x([1000.0, 2000.0], [1.0, 2.0], N, E)
    np.testing.assert_array_equal(y, [1.0, 2.0])


def test_input_not_modified_and_same_quantity_copies() -> None:
    x = np.array([300.0, 400.0])
    xo, _ = convert_x(x, [1.0, 2.0], W, W)
    xo[0] = 0.0
    assert x[0] == 300.0


@pytest.mark.parametrize("bad", [0.0, -1.0, np.nan, np.inf])
def test_non_positive_raises(bad: float) -> None:
    with pytest.raises(NonPositiveValue, match="greater than zero"):
        convert_x([500.0, bad], [1.0, 2.0], W, N)


def test_error_hierarchy_and_bad_arguments() -> None:
    assert issubclass(NonPositiveValue, GraphingError)
    with pytest.raises(IncompatibleXQuantity):
        convert_x([1.0], [1.0], "nm", E)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="shape"):
        convert_x([1.0, 2.0], [1.0], W, E)


def test_constants() -> None:
    assert constants.HC_EV_NM == pytest.approx(1239.841984, rel=1e-9)
    assert constants.EV_TO_CM1 == pytest.approx(8065.543937, rel=1e-9)
