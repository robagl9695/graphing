# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for core.interval (T1.5)."""

import itertools

import pytest

from graphing.core.errors import InvalidInterval
from graphing.core.interval import Interval
from graphing.core.units import Quantity, Unit

W, N, E = Quantity.WAVELENGTH, Quantity.WAVENUMBER, Quantity.ENERGY
UNITS = {W: Unit.NM, N: Unit.CM1, E: Unit.EV}


@pytest.mark.parametrize(
    ("args", "text"),
    [
        ((500.0, 400.0, W, Unit.NM), "must be below"),
        ((400.0, 400.0, W, Unit.NM), "must be below"),
        ((float("nan"), 400.0, W, Unit.NM), "finite"),
        ((400.0, float("inf"), W, Unit.NM), "finite"),
        ((-1.0, 400.0, W, Unit.NM), "greater than zero"),
        ((0.0, 400.0, W, Unit.NM), "greater than zero"),
        ((1.0, 2.0, Quantity.ABSORBANCE, Unit.DIMENSIONLESS), "not an x quantity"),
        ((1.0, 2.0, W, Unit.EV), "does not belong"),
    ],
)
def test_invalid_intervals(args: tuple, text: str) -> None:  # type: ignore[type-arg]
    with pytest.raises(InvalidInterval, match=text):
        Interval(*args)


def test_is_immutable() -> None:
    iv = Interval(400, 500, W, Unit.NM)
    with pytest.raises(AttributeError):
        iv.low = 1.0  # type: ignore[misc]
    assert isinstance(iv.low, float)


def test_to_swaps_ends_for_wavelength() -> None:
    iv = Interval(400, 500, W, Unit.NM)
    ev = iv.to(Unit.EV)
    assert ev.quantity is E
    assert ev.low == pytest.approx(2.479684, rel=1e-6)
    assert ev.high == pytest.approx(3.099605, rel=1e-6)
    assert iv.low == 400.0  # the original is not changed
    cm1 = iv.to(Unit.CM1)
    assert (cm1.low, cm1.high) == pytest.approx((20000.0, 25000.0), rel=1e-12)


def test_to_keeps_order_between_wavenumber_and_energy() -> None:
    iv = Interval(10000, 20000, N, Unit.CM1).to(Unit.EV)
    assert iv.low < iv.high
    assert iv.low == pytest.approx(10000 / 8065.543937, rel=1e-8)


@pytest.mark.parametrize(("a", "b"), list(itertools.permutations([W, N, E], 2)))
def test_round_trip(a: Quantity, b: Quantity) -> None:
    iv = Interval(300.0, 700.0, a, UNITS[a])
    back = iv.to(UNITS[b]).to(UNITS[a])
    assert (back.low, back.high) == pytest.approx((300.0, 700.0), rel=1e-12)


def test_to_same_unit_and_non_x_unit() -> None:
    iv = Interval(1.0, 2.0, E, Unit.EV)
    assert iv.to(Unit.EV) == iv
    with pytest.raises(InvalidInterval, match="not an x unit"):
        iv.to(Unit.PERCENT)
