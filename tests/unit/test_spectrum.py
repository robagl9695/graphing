# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for core.spectrum (T1.3)."""

import numpy as np
import pytest

from graphing.core.data import CurveData, StickData
from graphing.core.errors import InvalidData
from graphing.core.spectrum import Origin, Series, Spectrum, Technique
from graphing.core.units import Quantity, Unit


def curve() -> CurveData:
    return CurveData(
        x=np.array([200.0, 300.0]),
        y=np.array([0.1, 0.2]),
        x_quantity=Quantity.WAVELENGTH,
        x_unit=Unit.NM,
        y_quantity=Quantity.ABSORBANCE,
        y_unit=Unit.DIMENSIONLESS,
    )


def sticks() -> StickData:
    return StickData(
        x=np.array([250.0]),
        y=np.array([0.3]),
        x_quantity=Quantity.WAVELENGTH,
        x_unit=Unit.NM,
        y_quantity=Quantity.OSCILLATOR_STRENGTH,
        y_unit=Unit.DIMENSIONLESS,
    )


def spectrum(data: CurveData | StickData, origin: Origin) -> Spectrum:
    return Spectrum(name="a", data=data, technique=Technique.UV_VIS, origin=origin)


def test_metadata_read_only_and_copied() -> None:
    src = {"file": "a.txt"}
    sp = Spectrum(
        name="a",
        data=curve(),
        metadata=src,
        technique=Technique.UV_VIS,
        origin=Origin.EXPERIMENTAL,
    )
    src["file"] = "changed"
    assert sp.metadata["file"] == "a.txt"
    with pytest.raises(TypeError):
        sp.metadata["x"] = "y"  # type: ignore[index]
    with pytest.raises(AttributeError):
        sp.name = "b"  # type: ignore[misc]


def test_sticks_require_theoretical_origin() -> None:
    spectrum(sticks(), Origin.THEORETICAL)
    with pytest.raises(InvalidData, match="theoretical"):
        spectrum(sticks(), Origin.EXPERIMENTAL)


@pytest.mark.parametrize("origin", list(Origin))
def test_curve_may_be_either_origin(origin: Origin) -> None:
    spectrum(curve(), origin)


def test_invalid_data_and_metadata() -> None:
    with pytest.raises(InvalidData, match="CurveData or StickData"):
        Series(name="x", data=[1, 2])  # type: ignore[arg-type]
    with pytest.raises(InvalidData, match="text"):
        Series(name="x", data=curve(), metadata={"n": 1})  # type: ignore[dict-item]


def test_equality_and_hash() -> None:
    a = spectrum(curve(), Origin.EXPERIMENTAL)
    assert a == spectrum(curve(), Origin.EXPERIMENTAL)
    assert hash(a) == hash(spectrum(curve(), Origin.EXPERIMENTAL))
    assert a != spectrum(curve(), Origin.THEORETICAL)
    assert Series(name="a", data=curve()) != a
