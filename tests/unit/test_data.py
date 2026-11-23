# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for core.data (T1.3)."""

from typing import Any

import numpy as np
import pytest

from graphing.core.data import CurveData, StickData
from graphing.core.errors import InvalidData, InvalidUnit
from graphing.core.units import Quantity, Unit


def make(cls: type = CurveData, **over: Any) -> Any:
    args: dict[str, Any] = {
        "x": np.array([200.0, 300.0, 400.0]),
        "y": np.array([0.1, 0.5, 0.2]),
        "x_quantity": Quantity.WAVELENGTH,
        "x_unit": Unit.NM,
        "y_quantity": Quantity.ABSORBANCE,
        "y_unit": Unit.DIMENSIONLESS,
    }
    args.update(over)
    return cls(**args)


@pytest.mark.parametrize(
    ("over", "error", "text"),
    [
        ({"y": np.array([1.0, 2.0])}, InvalidData, "x has 3"),
        (
            {"x": np.array([[1.0, 2.0]]), "y": np.array([[1.0, 2.0]])},
            InvalidData,
            "one-dim",
        ),
        ({"x": np.array([1.0, np.nan, 3.0])}, InvalidData, "non-finite"),
        ({"y": np.array([1.0, np.inf, 3.0])}, InvalidData, "non-finite"),
        ({"x": np.array([3.0, 2.0, 1.0])}, InvalidData, "ascending"),
        ({"x": np.array([1.0, 1.0, 2.0])}, InvalidData, "ascending"),
        ({"x": np.array([1.0]), "y": np.array([1.0])}, InvalidData, "at least 2"),
        ({"x_quantity": Quantity.ABSORBANCE}, InvalidData, "x quantity"),
        ({"y_quantity": Quantity.ENERGY}, InvalidData, "y quantity"),
        ({"y_quantity": Quantity.NORMALISED_INTENSITY}, InvalidData, "normalised"),
        ({"x_unit": Unit.EV}, InvalidUnit, "does not belong"),
        ({"y_unit": Unit.PERCENT}, InvalidUnit, "does not belong"),
    ],
)
def test_validation_errors(
    over: dict[str, Any], error: type[Exception], text: str
) -> None:
    with pytest.raises(error, match=text):
        make(**over)


def test_stick_accepts_one_point() -> None:
    s = make(StickData, x=np.array([300.0]), y=np.array([0.2]))
    assert s.x.size == 1


def test_arrays_read_only_and_copied() -> None:
    x = np.array([1.0, 2.0, 3.0])
    d = make(x=x)
    x[0] = 99.0
    assert d.x[0] == 1.0
    assert not d.x.flags.writeable
    with pytest.raises(ValueError, match="read-only"):
        d.y[0] = 5.0
    with pytest.raises(AttributeError):
        d.x = np.array([1.0, 2.0])


def test_curve_and_stick_are_distinct_types() -> None:
    c = make(CurveData)
    s = make(StickData)
    assert not isinstance(c, StickData)
    assert not isinstance(s, CurveData)
    assert c != s


def test_equality_and_hash() -> None:
    a, b = make(), make()
    assert a == b
    assert hash(a) == hash(b)
    assert a != make(y=np.array([0.1, 0.5, 0.3]))
    assert a != make(y_quantity=Quantity.INTENSITY, y_unit=Unit.ARBITRARY)
    assert a != "curve"
