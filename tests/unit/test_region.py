# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for core.region (T1.5)."""

import numpy as np
import pytest

from graphing.core.data import CurveData, StickData
from graphing.core.errors import EmptySelection, InvalidInterval
from graphing.core.interval import Interval
from graphing.core.region import check_view_limits, crop, select_mask
from graphing.core.spectrum import Origin, Spectrum, Technique
from graphing.core.units import Quantity, Unit

W = Quantity.WAVELENGTH
NM_X = np.arange(200.0, 801.0, 50.0)  # 13 points
NM_Y = np.linspace(0.0, 1.0, NM_X.size)


def curve_nm() -> CurveData:
    return CurveData(
        x=NM_X,
        y=NM_Y,
        x_quantity=W,
        x_unit=Unit.NM,
        y_quantity=Quantity.ABSORBANCE,
        y_unit=Unit.DIMENSIONLESS,
    )


def curve_cm1() -> CurveData:
    """The same points as ``curve_nm`` with x in cm-1 (so ascending in cm-1)."""
    return CurveData(
        x=(1e7 / NM_X)[::-1],
        y=NM_Y[::-1],
        x_quantity=Quantity.WAVENUMBER,
        x_unit=Unit.CM1,
        y_quantity=Quantity.ABSORBANCE,
        y_unit=Unit.DIMENSIONLESS,
    )


def sticks_nm() -> StickData:
    return StickData(
        x=np.array([250.0, 350.0, 600.0]),
        y=np.array([0.1, 0.4, 0.2]),
        x_quantity=W,
        x_unit=Unit.NM,
        y_quantity=Quantity.OSCILLATOR_STRENGTH,
        y_unit=Unit.DIMENSIONLESS,
    )


IV = Interval(300.0, 500.0, W, Unit.NM)


def test_crop_is_inclusive_and_returns_a_new_object() -> None:
    original = curve_nm()
    out = crop(original, IV)
    assert out is not original
    np.testing.assert_array_equal(out.x, [300, 350, 400, 450, 500])
    np.testing.assert_array_equal(out.y, NM_Y[2:7])
    assert not out.x.flags.writeable
    # raw data intact
    np.testing.assert_array_equal(original.x, NM_X)
    np.testing.assert_array_equal(original.y, NM_Y)


def test_crop_spectrum_keeps_everything_else() -> None:
    sp = Spectrum(
        name="a",
        data=curve_nm(),
        metadata={"file": "a.txt"},
        technique=Technique.UV_VIS,
        origin=Origin.EXPERIMENTAL,
    )
    out = crop(sp, IV)
    assert isinstance(out, Spectrum)
    assert (out.name, out.technique, out.origin) == (
        "a",
        Technique.UV_VIS,
        Origin.EXPERIMENTAL,
    )
    assert out.metadata["file"] == "a.txt"
    assert out.data.x.size == 5
    assert sp.data.x.size == 13


@pytest.mark.parametrize("unit", [Unit.NM, Unit.CM1, Unit.EV])
@pytest.mark.parametrize("data_factory", [curve_nm, curve_cm1], ids=["nm", "cm1"])
def test_result_does_not_depend_on_interval_unit_or_data_unit(
    unit: Unit, data_factory: object
) -> None:
    out = crop(data_factory(), IV.to(unit))  # type: ignore[operator]
    in_nm = np.sort(1e7 / out.x) if out.x_unit is Unit.CM1 else out.x
    np.testing.assert_allclose(in_nm, [300, 350, 400, 450, 500], rtol=1e-12)


def test_ends_exactly_on_points_survive_conversion() -> None:
    """Every pair of ends taken from the data keeps both end points, in every unit."""
    for i in range(NM_X.size - 2):
        iv = Interval(NM_X[i], NM_X[i + 2], W, Unit.NM)
        for unit in (Unit.NM, Unit.CM1, Unit.EV):
            assert select_mask(curve_nm(), iv.to(unit)).sum() == 3


def test_sticks_crop_and_single_stick() -> None:
    out = crop(sticks_nm(), Interval(300.0, 400.0, W, Unit.NM))
    assert isinstance(out, StickData)
    np.testing.assert_array_equal(out.x, [350.0])


def test_empty_selection_errors() -> None:
    far = Interval(900.0, 1000.0, W, Unit.NM)
    with pytest.raises(EmptySelection, match="spans 200–800 nm"):
        crop(curve_nm(), far)
    with pytest.raises(EmptySelection):
        crop(sticks_nm(), far)
    one_point = Interval(310.0, 360.0, W, Unit.NM)  # holds only 350
    with pytest.raises(EmptySelection, match="at least|fewer than 2"):
        crop(curve_nm(), one_point)
    assert crop(sticks_nm(), one_point).x.tolist() == [350.0]


def test_view_limits() -> None:
    assert check_view_limits(0, 2) == (0.0, 2.0)
    assert check_view_limits(-1.5, 3.0) == (-1.5, 3.0)
    for low, high in [(2, 1), (1, 1), (float("nan"), 1), (0, float("inf"))]:
        with pytest.raises(InvalidInterval):
            check_view_limits(low, high)
