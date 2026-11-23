# SPDX-License-Identifier: GPL-3.0-or-later
"""Absorptivity and Beer–Lambert conversions (T3.4 AC1, AC2; D-20261122-08)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from model_helpers import CM1, NM, curve, uv_sticks

from graphing.core.broadening import broaden, profile_peak
from graphing.core.constants import (
    EV_TO_CM1,
    INTEGRATED_ABSORPTIVITY_PER_F,
    INTEGRATED_ABSORPTIVITY_PER_KM_MOL,
)
from graphing.core.data import StickData
from graphing.core.errors import InvalidTransform, NonPositiveValue
from graphing.core.evaluate import layer_values
from graphing.core.model import Broadening, Layer, LineShape, Panel
from graphing.core.operations import add_layer, add_y_transform, set_x_quantity
from graphing.core.spectrum import Origin, Spectrum, Technique
from graphing.core.transforms import (
    AbsorbanceToAbsorptivity,
    AbsorbanceToTransmittance,
    AbsorptivityToAbsorbance,
    IRIntensityToAbsorptivity,
    OscillatorStrengthToAbsorptivity,
    apply_transforms,
)
from graphing.core.units import Quantity, Unit

# Area tolerance of AC1. The auto grid (step FWHM/50, ±5 FWHM) integrates a Gaussian
# with the trapezoid rule far better than this.
AC1_RTOL = 1e-4


def one_line(
    position: float, height: float, quantity: Quantity, technique: Technique
) -> Spectrum:
    y_quantity = (
        Quantity.OSCILLATOR_STRENGTH
        if technique is Technique.UV_VIS
        else Quantity.IR_INTENSITY
    )
    data = StickData(
        x=np.array([position]),
        y=np.array([height]),
        x_quantity=quantity,
        x_unit={CM1: Unit.CM1, Quantity.ENERGY: Unit.EV, NM: Unit.NM}[quantity],
        y_quantity=y_quantity,
        y_unit=Unit.DIMENSIONLESS if technique is Technique.UV_VIS else Unit.KM_MOL,
    )
    return Spectrum(
        name="line", data=data, technique=technique, origin=Origin.THEORETICAL
    )


def epsilon_layer(spectrum: Spectrum, broadening: Broadening) -> tuple[Panel, Layer]:
    panel = Panel()
    layer = add_layer(panel, spectrum, broadening=broadening)
    transform = (
        OscillatorStrengthToAbsorptivity()
        if spectrum.technique is Technique.UV_VIS
        else IRIntensityToAbsorptivity()
    )
    add_y_transform(panel, layer, transform)
    set_x_quantity(panel, CM1, Unit.CM1)
    return panel, layer


class TestConstants:
    def test_f_constant_from_codata(self) -> None:
        r_e_cm, n_a = 2.8179403262e-13, 6.02214076e23
        expected = math.pi * r_e_cm * n_a / (1000.0 * math.log(10.0))
        assert INTEGRATED_ABSORPTIVITY_PER_F == pytest.approx(expected, rel=1e-15)
        assert 1.0 / INTEGRATED_ABSORPTIVITY_PER_F == pytest.approx(4.3190e-9, rel=1e-4)

    def test_km_mol_constant(self) -> None:
        assert INTEGRATED_ABSORPTIVITY_PER_KM_MOL == 100.0 / math.log(10.0)


class TestAC1Area:
    """The ε curve of one line integrates over cm⁻¹ to its intensity × constant."""

    @pytest.mark.parametrize(
        ("position", "quantity", "fwhm", "unit"),
        [
            (3.1, Quantity.ENERGY, 0.3, Unit.EV),
            (25000.0, CM1, 2500.0, Unit.CM1),
            (400.0, NM, 0.25, Unit.EV),
        ],
    )
    def test_uv_vis(
        self, position: float, quantity: Quantity, fwhm: float, unit: Unit
    ) -> None:
        f = 0.37
        b = Broadening(line_shape=LineShape.GAUSSIAN, fwhm=fwhm, fwhm_unit=unit)
        panel, layer = epsilon_layer(
            one_line(position, f, quantity, Technique.UV_VIS), b
        )
        values = layer_values(layer, panel)
        area = np.trapezoid(values.y, values.x)
        assert area / INTEGRATED_ABSORPTIVITY_PER_F == pytest.approx(f, rel=AC1_RTOL)

    def test_ir(self) -> None:
        a_km_mol = 210.3
        b = Broadening(line_shape=LineShape.GAUSSIAN, fwhm=12.0, fwhm_unit=Unit.CM1)
        panel, layer = epsilon_layer(one_line(1655.4, a_km_mol, CM1, Technique.IR), b)
        values = layer_values(layer, panel)
        area = np.trapezoid(values.y, values.x)
        assert area / INTEGRATED_ABSORPTIVITY_PER_KM_MOL == pytest.approx(
            a_km_mol, rel=AC1_RTOL
        )

    @pytest.mark.parametrize("unit", [Unit.CM1, Unit.EV])
    def test_lorentzian_on_a_wide_grid(self, unit: Unit) -> None:
        # ±6000 FWHM keeps all but 1/(6000 π) = 5.3e-5 of a Lorentzian's area; the
        # line is narrow so the grid stays above zero.
        fwhm = 3.0 if unit is Unit.CM1 else 0.0004
        centre = 25000.0 if unit is Unit.CM1 else 3.1
        quantity = CM1 if unit is Unit.CM1 else Quantity.ENERGY
        b = Broadening(line_shape=LineShape.LORENTZIAN, fwhm=fwhm, fwhm_unit=unit)
        line = one_line(centre, 0.5, quantity, Technique.UV_VIS).data
        assert isinstance(line, StickData)
        grid = centre + fwhm * np.linspace(-6000.0, 6000.0, 240_001)
        assert grid[0] > 0
        y = broaden(line, b, grid).y
        eps = OscillatorStrengthToAbsorptivity().apply(grid, y, quantity)
        grid_cm1 = grid * (EV_TO_CM1 if unit is Unit.EV else 1.0)
        area = np.trapezoid(eps, grid_cm1)
        assert area / INTEGRATED_ABSORPTIVITY_PER_F == pytest.approx(0.5, rel=AC1_RTOL)


class TestSticksOnEpsilon:
    """A stick on an ε axis is the maximum of its band alone (D-20261122-08)."""

    @pytest.mark.parametrize(
        "shape", [LineShape.GAUSSIAN, LineShape.LORENTZIAN, LineShape.VOIGT]
    )
    def test_stick_is_the_band_maximum(self, shape: LineShape) -> None:
        b = Broadening(
            line_shape=shape,
            fwhm=0.3,
            fwhm_unit=Unit.EV,
            fwhm_lorentzian=0.1 if shape is LineShape.VOIGT else None,
            step=0.3 / 600,
        )
        panel, layer = epsilon_layer(
            one_line(3.0, 0.2, Quantity.ENERGY, Technique.UV_VIS), b
        )
        values = layer_values(layer, panel)
        assert values.sticks is not None
        assert values.sticks[1][0] == pytest.approx(values.y.max(), rel=1e-5)

    def test_gaussian_peak_matches_the_thesis_form(self) -> None:
        # ε_max = K f / (σ' √π) with exp[-(ν̃/σ')²], σ' = FWHM / (2 √ln 2).
        fwhm = 3000.0
        b = Broadening(line_shape=LineShape.GAUSSIAN, fwhm=fwhm, fwhm_unit=Unit.CM1)
        sigma_prime = fwhm / (2.0 * math.sqrt(math.log(2.0)))
        expected = INTEGRATED_ABSORPTIVITY_PER_F / (sigma_prime * math.sqrt(math.pi))
        assert profile_peak(b) * INTEGRATED_ABSORPTIVITY_PER_F == pytest.approx(
            expected, rel=1e-12
        )

    def test_view_does_not_change_epsilon(self) -> None:
        b = Broadening(line_shape=LineShape.GAUSSIAN, fwhm=0.3, fwhm_unit=Unit.EV)
        panel, layer = epsilon_layer(uv_sticks(), b)
        in_cm1 = layer_values(layer, panel)
        set_x_quantity(panel, NM, Unit.NM)
        in_nm = layer_values(layer, panel)
        np.testing.assert_array_equal(np.sort(in_nm.y), np.sort(in_cm1.y))
        assert in_nm.sticks is not None and in_cm1.sticks is not None
        np.testing.assert_array_equal(
            np.sort(in_nm.sticks[1]), np.sort(in_cm1.sticks[1])
        )

    def test_chain_to_transmittance_keeps_sticks_with_the_curve(self) -> None:
        b = Broadening(line_shape=LineShape.GAUSSIAN, fwhm=0.3, fwhm_unit=Unit.EV)
        panel, layer = epsilon_layer(
            one_line(3.0, 0.2, Quantity.ENERGY, Technique.UV_VIS), b
        )
        eps = layer_values(layer, panel)
        add_y_transform(panel, layer, AbsorptivityToAbsorbance(1.0, 1e-5))
        add_y_transform(panel, layer, AbsorbanceToTransmittance())
        shown = layer_values(layer, panel)
        assert shown.sticks is not None and eps.sticks is not None
        np.testing.assert_allclose(shown.y, 10.0 ** (2.0 - eps.y * 1e-5), rtol=1e-12)
        np.testing.assert_allclose(
            shown.sticks[1], 10.0 ** (2.0 - eps.sticks[1] * 1e-5), rtol=1e-12
        )


class TestCurveLayers:
    def test_curve_in_cm1_is_a_density_per_cm1(self) -> None:
        x = np.linspace(20000.0, 30000.0, 11)
        spectrum = curve(
            x,
            np.full(11, 1e-4),
            x_quantity=CM1,
            y_quantity=Quantity.OSCILLATOR_STRENGTH,
        )
        panel = Panel()
        layer = add_layer(panel, spectrum)
        add_y_transform(panel, layer, OscillatorStrengthToAbsorptivity())
        set_x_quantity(panel, NM, Unit.NM)
        y = layer_values(layer, panel).y
        np.testing.assert_allclose(y, 1e-4 * INTEGRATED_ABSORPTIVITY_PER_F, rtol=1e-15)

    def test_curve_stored_in_nm_has_no_defined_density(self) -> None:
        with pytest.raises(InvalidTransform, match="per cm⁻¹ or per eV"):
            OscillatorStrengthToAbsorptivity().apply(
                np.array([400.0]), np.array([1.0]), NM
            )

    def test_wrong_source_quantity(self) -> None:
        with pytest.raises(InvalidTransform):
            IRIntensityToAbsorptivity().result_quantity(Quantity.OSCILLATOR_STRENGTH)
        with pytest.raises(InvalidTransform):
            AbsorptivityToAbsorbance(1.0, 1.0).result_quantity(Quantity.ABSORBANCE)
        with pytest.raises(InvalidTransform):
            AbsorbanceToAbsorptivity(1.0, 1.0).result_quantity(
                Quantity.MOLAR_ABSORPTIVITY
            )


class TestAC2BeerLambert:
    def test_round_trip_is_identity(self) -> None:
        rng = np.random.default_rng(34)
        x = np.linspace(200.0, 800.0, 601)
        a = rng.uniform(0.0, 3.0, x.size)
        b_cm, c_mol_l = 0.1, 2.5e-5
        y, quantity = apply_transforms(
            x,
            a,
            NM,
            Quantity.ABSORBANCE,
            [
                AbsorbanceToAbsorptivity(b_cm, c_mol_l),
                AbsorptivityToAbsorbance(b_cm, c_mol_l),
            ],
        )
        assert quantity is Quantity.ABSORBANCE
        np.testing.assert_allclose(y, a, rtol=1e-12)

    def test_values(self) -> None:
        y, quantity = apply_transforms(
            np.array([1.0]),
            np.array([0.5]),
            NM,
            Quantity.ABSORBANCE,
            [AbsorbanceToAbsorptivity(1.0, 1e-4)],
        )
        assert quantity is Quantity.MOLAR_ABSORPTIVITY
        assert y[0] == pytest.approx(5000.0, rel=1e-15)

    @pytest.mark.parametrize("bad", [0.0, -1.0, math.nan, math.inf])
    @pytest.mark.parametrize(
        "cls", [AbsorptivityToAbsorbance, AbsorbanceToAbsorptivity]
    )
    def test_non_positive_b_or_c_raise(self, cls: type, bad: float) -> None:
        with pytest.raises(NonPositiveValue, match="path length"):
            cls(bad, 1e-4)
        with pytest.raises(NonPositiveValue, match="concentration"):
            cls(1.0, bad)
