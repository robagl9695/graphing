# SPDX-License-Identifier: GPL-3.0-or-later
"""E3 integration: program output → load → layer with broadening → ε → A → %T.

Every theoretical corpus file that must load goes through the public interfaces of
``core/`` only (``io.load``, ``operations``, ``evaluate.layer_values``), with the
broadening the corpus gallery uses: Gaussian, FWHM 250 meV, for UV-Vis and
Lorentzian, FWHM 4 cm⁻¹, for IR (Rob, S019). Gate 0.1.0: "sticks from any parser
become a physically correct curve".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from graphing.core.broadening import broaden, broadened_lines
from graphing.core.constants import (
    INTEGRATED_ABSORPTIVITY_PER_F,
    INTEGRATED_ABSORPTIVITY_PER_KM_MOL,
)
from graphing.core.data import StickData
from graphing.core.evaluate import LayerValues, layer_values
from graphing.core.io import load
from graphing.core.model import Broadening, Layer, LineShape, Panel
from graphing.core.operations import (
    add_layer,
    add_y_transform,
    set_broadening,
    set_x_quantity,
)
from graphing.core.spectrum import Origin, Series, Spectrum, Technique
from graphing.core.transforms import (
    AbsorbanceToTransmittance,
    AbsorptivityToAbsorbance,
    IRIntensityToAbsorptivity,
    LinesToAbsorptivity,
    OscillatorStrengthToAbsorptivity,
)
from graphing.core.units import DEFAULT_UNIT, Quantity, Unit, convert_x

pytestmark = pytest.mark.integration

CORPUS = Path(__file__).resolve().parents[1] / "corpus" / "theoretical"

UV_BROADENING = Broadening(line_shape=LineShape.GAUSSIAN, fwhm=0.250, fwhm_unit=Unit.EV)
IR_BROADENING = Broadening(
    line_shape=LineShape.LORENTZIAN, fwhm=4.0, fwhm_unit=Unit.CM1
)

AREA_RTOL = 1e-4  # as T3.2 AC1 and T3.4 AC1
EXACT_RTOL = 1e-12  # the same numbers computed along two routes
PATH_LENGTH_CM = 1.0
CONCENTRATION_MOL_L = 1e-5


@dataclass(frozen=True)
class Case:
    file: str
    format_id: str
    technique: Technique

    @property
    def broadening(self) -> Broadening:
        return UV_BROADENING if self.technique is Technique.UV_VIS else IR_BROADENING

    @property
    def constant(self) -> float:
        if self.technique is Technique.UV_VIS:
            return INTEGRATED_ABSORPTIVITY_PER_F
        return INTEGRATED_ABSORPTIVITY_PER_KM_MOL

    def to_epsilon(self) -> LinesToAbsorptivity:
        if self.technique is Technique.UV_VIS:
            return OscillatorStrengthToAbsorptivity()
        return IRIntensityToAbsorptivity()


CASES = [
    Case("synthetic-3bands.out", "orca", Technique.UV_VIS),
    Case("synthetic-shoulder.out", "orca", Technique.UV_VIS),
    Case("synthetic-wave.out", "orca", Technique.UV_VIS),
    Case("artificial.exspectrum", "turbomole-exspectrum", Technique.UV_VIS),
    Case("imaginary-mode.vibspectrum", "turbomole-vibspectrum", Technique.IR),
]
IDS = [case.file for case in CASES]
UV_CASES = [case for case in CASES if case.technique is Technique.UV_VIS]


def load_sticks(case: Case) -> Spectrum:
    (spectrum,) = load(
        CORPUS / case.file, case.technique, Origin.THEORETICAL, case.format_id
    )
    assert isinstance(spectrum.data, StickData)
    return spectrum


def epsilon_panel(
    case: Case, broadening: Broadening | None = None
) -> tuple[Panel, Layer]:
    """One panel, one layer of the file, on ε, x in cm⁻¹."""
    panel = Panel()
    layer = add_layer(
        panel, load_sticks(case), broadening=broadening or case.broadening
    )
    add_y_transform(panel, layer, case.to_epsilon())
    set_x_quantity(panel, Quantity.WAVENUMBER, Unit.CM1)
    return panel, layer


def drawn_heights(spectrum: Series) -> np.ndarray:
    data = spectrum.data
    assert isinstance(data, StickData)
    return np.asarray(data.y[broadened_lines(data)], dtype=np.float64)


def sticks_of(values: LayerValues) -> tuple[np.ndarray, np.ndarray]:
    assert values.sticks is not None
    return values.sticks[0], values.sticks[1]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_every_file_becomes_a_finite_curve_with_its_sticks(case: Case) -> None:
    panel, layer = epsilon_panel(case)
    values = layer_values(layer, panel)
    assert values.x.size > 1 and np.all(np.diff(values.x) > 0)
    assert np.all(np.isfinite(values.y)) and np.all(values.y >= 0)
    assert values.y.max() > 0
    stick_x, stick_y = sticks_of(values)
    assert stick_x.size == drawn_heights(layer.source).size
    assert np.all(stick_x > 0) and np.all(np.isfinite(stick_y))


def test_imaginary_mode_is_neither_broadened_nor_drawn() -> None:
    case = CASES[-1]
    spectrum = load_sticks(case)
    data = spectrum.data
    assert isinstance(data, StickData)
    assert np.any(data.x < 0)  # the file has one, the reader keeps it
    panel, layer = epsilon_panel(case)
    values = layer_values(layer, panel)
    stick_x, _ = sticks_of(values)
    assert stick_x.size == int(np.count_nonzero(data.x > 0))
    assert np.all(stick_x > 0) and values.x.min() > 0


@pytest.mark.parametrize("case", UV_CASES, ids=[c.file for c in UV_CASES])
def test_uv_area_of_epsilon_gives_back_the_oscillator_strengths(case: Case) -> None:
    # Broadened in eV, shown in cm⁻¹: ∫ε dν̃ = K Σ f over the drawn lines. A Gaussian
    # keeps all its area inside the automatic ±5 FWHM grid.
    panel, layer = epsilon_panel(case)
    values = layer_values(layer, panel)
    area = np.trapezoid(values.y, values.x)
    expected = case.constant * drawn_heights(layer.source).sum()
    assert area == pytest.approx(expected, rel=AREA_RTOL)


def test_ir_area_of_epsilon_gives_back_the_intensities() -> None:
    # A Lorentzian keeps ~94 % of its area inside the automatic grid (a display
    # choice, broadening.RANGE_IN_FWHM), so the area is taken on a wide grid and the
    # chain is checked against the same broadening point by point.
    case = CASES[-1]
    spectrum = load_sticks(case)
    data = spectrum.data
    assert isinstance(data, StickData)
    fwhm = case.broadening.fwhm
    step = fwhm / 50.0
    grid = np.arange(-6000.0 * fwhm, 4000.0 + 6000.0 * fwhm, step)
    wide = broaden(data, case.broadening, grid)
    area = case.constant * np.trapezoid(wide.y, wide.x)
    assert area == pytest.approx(
        case.constant * drawn_heights(spectrum).sum(), rel=AREA_RTOL
    )

    panel, layer = epsilon_panel(case)
    values = layer_values(layer, panel)
    direct = broaden(data, case.broadening, values.x)
    np.testing.assert_allclose(
        values.y, case.constant * direct.y, rtol=EXACT_RTOL, atol=0.0
    )


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_scale_factor_and_shift_move_curve_and_sticks_together(case: Case) -> None:
    factor = 0.95
    shift = 0.1 if case.technique is Technique.UV_VIS else 10.0  # eV or cm⁻¹
    panel, layer = epsilon_panel(case)
    before_x, before_y = sticks_of(layer_values(layer, panel))
    corrected = Broadening(
        line_shape=case.broadening.line_shape,
        fwhm=case.broadening.fwhm,
        fwhm_unit=case.broadening.fwhm_unit,
        scale_factor=factor,
        shift=shift,
    )
    set_broadening(layer, corrected)
    values = layer_values(layer, panel)
    after_x, after_y = sticks_of(values)

    # Positions corrected in the broadening unit, compared in cm⁻¹.
    own = Quantity.ENERGY if case.technique is Technique.UV_VIS else Quantity.WAVENUMBER
    before_own, _ = convert_x(before_x, before_y, Quantity.WAVENUMBER, own)
    after_own, _ = convert_x(after_x, after_y, Quantity.WAVENUMBER, own)
    np.testing.assert_allclose(after_own, factor * before_own + shift, rtol=EXACT_RTOL)
    np.testing.assert_allclose(np.sort(after_y), np.sort(before_y), rtol=EXACT_RTOL)

    # The curve is the broadening of the corrected lines.
    data = layer.source.data
    assert isinstance(data, StickData)
    grid_own, y_view = convert_x(values.x, values.y, Quantity.WAVENUMBER, own)
    direct = broaden(data, corrected, grid_own)
    expected = case.to_epsilon().apply(grid_own, direct.y, own)
    np.testing.assert_allclose(y_view, expected, rtol=EXACT_RTOL, atol=0.0)


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_epsilon_to_absorbance_to_transmittance(case: Case) -> None:
    panel, layer = epsilon_panel(case)
    eps = layer_values(layer, panel)
    eps_sx, eps_sy = sticks_of(eps)

    add_y_transform(
        panel, layer, AbsorptivityToAbsorbance(PATH_LENGTH_CM, CONCENTRATION_MOL_L)
    )
    absorbance = layer_values(layer, panel)
    bc = PATH_LENGTH_CM * CONCENTRATION_MOL_L
    np.testing.assert_allclose(absorbance.y, eps.y * bc, rtol=EXACT_RTOL, atol=0.0)
    a_sx, a_sy = sticks_of(absorbance)
    np.testing.assert_array_equal(a_sx, eps_sx)
    np.testing.assert_allclose(a_sy, eps_sy * bc, rtol=EXACT_RTOL, atol=0.0)

    add_y_transform(panel, layer, AbsorbanceToTransmittance())
    transmittance = layer_values(layer, panel)
    np.testing.assert_allclose(
        transmittance.y, 10.0 ** (2.0 - absorbance.y), rtol=EXACT_RTOL, atol=0.0
    )
    assert np.all((transmittance.y > 0) & (transmittance.y <= 100.0))
    t_sx, t_sy = sticks_of(transmittance)
    np.testing.assert_array_equal(t_sx, a_sx)
    np.testing.assert_allclose(t_sy, 10.0 ** (2.0 - a_sy), rtol=EXACT_RTOL, atol=0.0)


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_curve_does_not_depend_on_the_view(case: Case) -> None:
    panel, layer = epsilon_panel(case)
    reference = layer_values(layer, panel)
    for quantity in (Quantity.WAVELENGTH, Quantity.ENERGY):
        set_x_quantity(panel, quantity, DEFAULT_UNIT[quantity])
        view = layer_values(layer, panel)
        back_x, back_y = convert_x(view.x, view.y, quantity, Quantity.WAVENUMBER)
        np.testing.assert_allclose(back_x, reference.x, rtol=EXACT_RTOL, atol=0.0)
        np.testing.assert_array_equal(back_y, reference.y)
        view_sx, view_sy = sticks_of(view)
        ref_sx, ref_sy = sticks_of(reference)
        sx, sy = convert_x(view_sx, view_sy, quantity, Quantity.WAVENUMBER)
        np.testing.assert_allclose(sx, ref_sx, rtol=EXACT_RTOL, atol=0.0)
        np.testing.assert_array_equal(sy, ref_sy)
        set_x_quantity(panel, Quantity.WAVENUMBER, Unit.CM1)


# Parsers with no corpus file yet: the ORCA IR block and Turbomole escf.out. Small
# synthetic texts in the layout the parsers read (values invented, not a molecule).
ORCA_IR = """                       Program Version 6.0.1  -  RELEASE   -
IR SPECTRUM
-----------

 Mode   freq       eps      Int      T**2         TX        TY        TZ
       cm**-1   L/(mol*cm) km/mol    a.u.
----------------------------------------------------------------------------
  6:    500.00   0.010000   50.00  0.100000  ( 0.100000  0.000000  0.000000)
  7:   1700.00   0.050000  250.00  0.500000  ( 0.000000  0.100000  0.000000)
  8:   3000.00   0.000000    0.00  0.000000  ( 0.000000  0.000000  0.000000)

* The epsilon (eps) is given for a Dirac delta lineshape.
"""


def escf_state(number: int, energy_cm1: float, fosc: float) -> str:
    return f"""
                         {number} singlet a excitation

 Excitation energy / cm^(-1):             {energy_cm1}

 Oscillator strength:

    velocity representation:             {fosc * 1.1:.16E}

    length representation:               {fosc:.16E}

 Rotatory strength:

    velocity representation:             0.1E-06
"""


ESCF = (
    " escf : TURBOMOLE V7.3.1 ()\n"
    + escf_state(1, 20000.0, 0.2)
    + escf_state(2, 25000.0, 0.4)
)

EXTRA = [
    # Mode 8 has zero intensity: still a stick (of height 0); only positions <= 0 go.
    (Case("orca-ir.out", "orca", Technique.IR), ORCA_IR, 3),
    (Case("escf.out", "turbomole-escf", Technique.UV_VIS), ESCF, 2),
]


@pytest.mark.parametrize(
    ("case", "text", "lines"), EXTRA, ids=[c.file for c, _, _ in EXTRA]
)
def test_parsers_without_corpus_file_give_a_correct_curve(
    case: Case, text: str, lines: int, tmp_path: Path
) -> None:
    path = tmp_path / case.file
    path.write_text(text, encoding="utf-8")
    (spectrum,) = load(path, case.technique, Origin.THEORETICAL, case.format_id)
    data = spectrum.data
    assert isinstance(data, StickData)
    panel = Panel()
    layer = add_layer(panel, spectrum, broadening=case.broadening)
    add_y_transform(panel, layer, case.to_epsilon())
    set_x_quantity(panel, Quantity.WAVENUMBER, Unit.CM1)
    values = layer_values(layer, panel)
    assert np.all(np.isfinite(values.y)) and np.all(values.y >= 0)
    stick_x, _ = sticks_of(values)
    assert stick_x.size == lines
    if case.technique is Technique.UV_VIS:
        area = np.trapezoid(values.y, values.x)
        expected = case.constant * drawn_heights(spectrum).sum()
        assert area == pytest.approx(expected, rel=AREA_RTOL)
    else:
        direct = broaden(data, case.broadening, values.x)
        np.testing.assert_allclose(
            values.y, case.constant * direct.y, rtol=EXACT_RTOL, atol=0.0
        )
