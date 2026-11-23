# SPDX-License-Identifier: GPL-3.0-or-later
"""Broadening sticks into a curve (T3.2)."""

from __future__ import annotations

import numpy as np
import pytest

from graphing.core.broadening import (
    RANGE_IN_FWHM,
    STEP_PER_FWHM,
    auto_grid,
    broaden,
    broaden_lines,
    broadened_lines,
    corrected_sticks,
    grid_step,
    profile_fwhm,
)
from graphing.core.data import StickData
from graphing.core.errors import InvalidData, NonPositiveValue
from graphing.core.lineshapes import voigt_fwhm
from graphing.core.model import Broadening, LineShape
from graphing.core.units import Quantity, Unit

GAUSS = Broadening(line_shape=LineShape.GAUSSIAN, fwhm=10.0, fwhm_unit=Unit.CM1)
LORENTZ = Broadening(line_shape=LineShape.LORENTZIAN, fwhm=10.0, fwhm_unit=Unit.CM1)
VOIGT = Broadening(
    line_shape=LineShape.VOIGT, fwhm=8.0, fwhm_unit=Unit.CM1, fwhm_lorentzian=4.0
)

# AC1 tolerance (ROUTE T3.2).
AREA_RTOL = 1e-4


def ir_sticks(x: list[float], y: list[float]) -> StickData:
    return StickData(
        x=np.array(x),
        y=np.array(y),
        x_quantity=Quantity.WAVENUMBER,
        x_unit=Unit.CM1,
        y_quantity=Quantity.IR_INTENSITY,
        y_unit=Unit.KM_MOL,
    )


def uv_sticks_nm(x: list[float], y: list[float]) -> StickData:
    return StickData(
        x=np.array(x),
        y=np.array(y),
        x_quantity=Quantity.WAVELENGTH,
        x_unit=Unit.NM,
        y_quantity=Quantity.OSCILLATOR_STRENGTH,
        y_unit=Unit.DIMENSIONLESS,
    )


def wide_grid(centre: float, b: Broadening, half_width_in_fwhm: float) -> np.ndarray:
    # A Lorentzian keeps 1 - (2/pi) atan(2k) of its area inside ±k FWHM: k = 1e4
    # loses 3.2e-5, below the AC1 tolerance.
    half = half_width_in_fwhm * profile_fwhm(b)
    step = profile_fwhm(b) / 20.0
    return centre + np.arange(-half, half + step / 2, step)


class TestAC1SingleStickArea:
    def test_gaussian_on_the_automatic_grid(self) -> None:
        curve = broaden(ir_sticks([1700.0], [123.4]), GAUSS)
        area = np.trapezoid(curve.y, curve.x)
        assert area == pytest.approx(123.4, rel=AREA_RTOL)

    @pytest.mark.parametrize("b", [LORENTZ, VOIGT], ids=["lorentzian", "voigt"])
    def test_lorentzian_tails_on_a_wide_grid(self, b: Broadening) -> None:
        grid = wide_grid(20000.0, b, 1e4)
        curve = broaden(ir_sticks([20000.0], [0.75]), b, grid=grid)
        area = np.trapezoid(curve.y, curve.x)
        assert area == pytest.approx(0.75, rel=AREA_RTOL)

    def test_uv_stick_in_nm_broadened_in_ev(self) -> None:
        b = Broadening(line_shape=LineShape.GAUSSIAN, fwhm=0.3, fwhm_unit=Unit.EV)
        curve = broaden(uv_sticks_nm([450.0], [0.2]), b)
        assert curve.x_quantity is Quantity.ENERGY and curve.x_unit is Unit.EV
        assert curve.y_quantity is Quantity.OSCILLATOR_STRENGTH
        assert np.trapezoid(curve.y, curve.x) == pytest.approx(0.2, rel=AREA_RTOL)


class TestAC3RepeatedLines:
    @pytest.mark.parametrize(
        "b", [GAUSS, LORENTZ, VOIGT], ids=["gaussian", "lorentzian", "voigt"]
    )
    def test_two_equal_positions_equal_one_summed_line(self, b: Broadening) -> None:
        grid = auto_grid([1500.0, 1700.0], b)
        pair = broaden(ir_sticks([1700.0, 1500.0, 1700.0], [30.0, 5.0, 12.0]), b, grid)
        single = broaden(ir_sticks([1500.0, 1700.0], [5.0, 42.0]), b, grid)
        np.testing.assert_allclose(pair.y, single.y, rtol=1e-12, atol=0.0)

    def test_file_order_does_not_matter(self) -> None:
        a = broaden(ir_sticks([1700.0, 1500.0, 1600.0], [1.0, 2.0, 3.0]), GAUSS)
        b = broaden(ir_sticks([1500.0, 1600.0, 1700.0], [2.0, 3.0, 1.0]), GAUSS)
        np.testing.assert_array_equal(a.x, b.x)
        np.testing.assert_allclose(a.y, b.y, rtol=1e-12, atol=0.0)


class TestGrid:
    def test_automatic_step_is_fwhm_over_50(self) -> None:
        assert grid_step(GAUSS) == pytest.approx(10.0 / STEP_PER_FWHM)
        assert STEP_PER_FWHM == 50.0
        assert grid_step(VOIGT) == pytest.approx(voigt_fwhm(8.0, 4.0) / 50.0)

    def test_explicit_step_is_kept(self) -> None:
        b = Broadening(
            line_shape=LineShape.GAUSSIAN, fwhm=10.0, fwhm_unit=Unit.CM1, step=0.5
        )
        assert grid_step(b) == 0.5

    def test_range_and_uniform_spacing(self) -> None:
        grid = auto_grid([1500.0, 1700.0], GAUSS)
        margin = RANGE_IN_FWHM * 10.0
        assert grid[0] == pytest.approx(1500.0 - margin)
        assert grid[-1] <= 1700.0 + margin
        assert grid[-1] > 1700.0 + margin - grid_step(GAUSS)
        np.testing.assert_allclose(np.diff(grid), grid_step(GAUSS), rtol=1e-9)

    def test_grid_stays_above_zero(self) -> None:
        grid = auto_grid([20.0], GAUSS)  # 20 - 50 would be negative
        assert grid[0] > 0
        assert grid[0] == pytest.approx(grid_step(GAUSS), rel=1e-9)

    def test_no_lines(self) -> None:
        with pytest.raises(InvalidData):
            auto_grid([], GAUSS)


class TestLines:
    def test_negative_positions_are_skipped(self) -> None:
        # An imaginary mode printed as a negative wavenumber is not broadened.
        with_imaginary = broaden(ir_sticks([-120.0, 1700.0], [50.0, 10.0]), GAUSS)
        without = broaden(ir_sticks([1700.0], [10.0]), GAUSS)
        np.testing.assert_array_equal(with_imaginary.y, without.y)

    def test_only_negative_positions(self) -> None:
        with pytest.raises(InvalidData):
            broaden(ir_sticks([-120.0], [50.0]), GAUSS)

    def test_lengths_must_match(self) -> None:
        with pytest.raises(InvalidData):
            broaden_lines([1.0, 2.0], [1.0], GAUSS, [1.0, 2.0])

    def test_peak_of_isolated_gaussian(self) -> None:
        # Height h, unit-area Gaussian: maximum h / (sigma sqrt(2 pi)).
        curve = broaden(ir_sticks([1700.0], [1.0]), GAUSS)
        sigma = 10.0 / (2.0 * np.sqrt(2.0 * np.log(2.0)))
        expected = 1.0 / (sigma * np.sqrt(2.0 * np.pi))
        # Sampled on a grid of FWHM/50: within 0.1 % of the true maximum.
        assert curve.y.max() == pytest.approx(expected, rel=1e-3)


# --- T3.3: scale factor and shift ---------------------------------------------------


def with_correction(
    b: Broadening, *, scale_factor: float = 1.0, shift: float = 0.0
) -> Broadening:
    return Broadening(
        line_shape=b.line_shape,
        fwhm=b.fwhm,
        fwhm_unit=b.fwhm_unit,
        fwhm_lorentzian=b.fwhm_lorentzian,
        scale_factor=scale_factor,
        shift=shift,
    )


class TestT33NoOp:
    """AC1: factor 1.0 and shift 0.0 change nothing."""

    def test_same_object_comes_back(self) -> None:
        sticks = ir_sticks([1500.0, 1700.0], [1.0, 2.0])
        assert corrected_sticks(sticks, GAUSS) is sticks

    @pytest.mark.parametrize("b", [GAUSS, LORENTZ, VOIGT])
    def test_curve_is_identical(self, b: Broadening) -> None:
        sticks = ir_sticks([1500.0, 1700.0], [1.0, 2.0])
        explicit = with_correction(b, scale_factor=1.0, shift=0.0)
        np.testing.assert_array_equal(broaden(sticks, b).y, broaden(sticks, explicit).y)


class TestT33Applied:
    """AC2: positions are corrected before broadening."""

    def test_factor_then_shift_in_wavenumber(self) -> None:
        sticks = ir_sticks([1000.0, 1700.0], [1.0, 2.0])
        b = with_correction(GAUSS, scale_factor=0.96, shift=-3.0)
        moved = corrected_sticks(sticks, b)
        np.testing.assert_allclose(moved.x, [957.0, 1629.0], rtol=1e-15)
        np.testing.assert_array_equal(moved.y, sticks.y)

    def test_curve_peak_follows_the_corrected_position(self) -> None:
        b = with_correction(GAUSS, scale_factor=0.96)
        curve = broaden(ir_sticks([1700.0], [10.0]), b)
        peak = curve.x[np.argmax(curve.y)]
        assert peak == pytest.approx(1632.0, abs=grid_step(b))

    def test_uv_sticks_in_nm_are_corrected_in_ev(self) -> None:
        b = Broadening(
            line_shape=LineShape.GAUSSIAN, fwhm=0.3, fwhm_unit=Unit.EV, shift=0.25
        )
        moved = corrected_sticks(uv_sticks_nm([400.0], [0.5]), b)
        assert moved.x_quantity is Quantity.ENERGY and moved.x_unit is Unit.EV
        ev = 1239.841984 / 400.0
        assert moved.x[0] == pytest.approx(ev + 0.25, rel=1e-6)

    def test_labels_survive(self) -> None:
        sticks = StickData(
            x=np.array([1000.0, 1100.0]),
            y=np.array([1.0, 2.0]),
            x_quantity=Quantity.WAVENUMBER,
            x_unit=Unit.CM1,
            y_quantity=Quantity.IR_INTENSITY,
            y_unit=Unit.KM_MOL,
            labels=("a", "b"),
        )
        moved = corrected_sticks(sticks, with_correction(GAUSS, scale_factor=0.9))
        assert moved.labels == ("a", "b")


class TestT33Invalid:
    """AC3: invalid values raise named errors."""

    @pytest.mark.parametrize("factor", [0.0, -0.96, float("nan"), float("inf")])
    def test_bad_factor(self, factor: float) -> None:
        with pytest.raises(NonPositiveValue):
            with_correction(GAUSS, scale_factor=factor)

    @pytest.mark.parametrize("shift", [float("nan"), float("inf"), -float("inf")])
    def test_bad_shift(self, shift: float) -> None:
        with pytest.raises(InvalidData):
            with_correction(GAUSS, shift=shift)


class TestT33NonPositiveLines:
    """AC4: imaginary lines are not moved; lines pushed to zero or below are dropped."""

    def test_imaginary_line_is_not_shifted_into_view(self) -> None:
        sticks = ir_sticks([-100.0, 1500.0], [1.0, 2.0])
        b = with_correction(GAUSS, shift=500.0)
        moved = corrected_sticks(sticks, b)
        np.testing.assert_array_equal(moved.x, [-100.0, 2000.0])
        np.testing.assert_array_equal(broadened_lines(moved), [False, True])

    def test_line_pushed_below_zero_is_dropped(self) -> None:
        sticks = ir_sticks([300.0, 1500.0], [1.0, 2.0])
        moved = corrected_sticks(sticks, with_correction(GAUSS, shift=-400.0))
        np.testing.assert_array_equal(broadened_lines(moved), [False, True])

    def test_all_lines_dropped_is_an_error(self) -> None:
        with pytest.raises(InvalidData):
            broaden(ir_sticks([300.0], [1.0]), with_correction(GAUSS, shift=-400.0))
