# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for core.transforms (T1.4)."""

import numpy as np
import pytest

from graphing.core.errors import (
    CannotNormalise,
    DivisionByZero,
    InvalidTransform,
    NonPositiveValue,
)
from graphing.core.transforms import (
    AbsorbanceToTransmittance,
    DerivedQuantity,
    Inverse,
    Level,
    Log10,
    NormaliseAtX,
    NormaliseToMax,
    TransmittanceToAbsorbance,
    YTransform,
    apply_transforms,
)
from graphing.core.units import Quantity, Unit

NM = Quantity.WAVELENGTH
X = np.array([200.0, 300.0, 400.0, 500.0])
Y = np.array([0.2, 0.8, 0.5, 0.1])


def run(t: YTransform, y: np.ndarray = Y, x: np.ndarray = X) -> np.ndarray:
    return t.apply(x, y, NM)


def test_normalise_to_max_is_exactly_one() -> None:
    rng = np.random.default_rng(3)
    y = rng.uniform(0.01, 7.3, 500)
    out = run(NormaliseToMax(), y, np.arange(1.0, 501.0))
    assert out.max() == 1.0
    np.testing.assert_allclose(out * y.max(), y, rtol=1e-15)


def test_normalise_at_x_interpolates_and_converts() -> None:
    out = run(NormaliseAtX(350.0, NM, Unit.NM))
    assert out[1] == pytest.approx(0.8 / 0.65)
    # 1e7/350 cm-1 is 350 nm; x array is in nm, so the reference is converted.
    cm1 = NormaliseAtX(1e7 / 350.0, Quantity.WAVENUMBER, Unit.CM1)
    np.testing.assert_allclose(run(cm1), out, rtol=1e-12)


def test_level_subtracts_constant() -> None:
    np.testing.assert_allclose(run(Level(0.1)), Y - 0.1)


def test_t_a_round_trip() -> None:
    t = np.random.default_rng(5).uniform(0.05, 100.0, 300)
    a = run(TransmittanceToAbsorbance(), t, np.arange(300.0) + 1)
    back = run(AbsorbanceToTransmittance(), a, np.arange(300.0) + 1)
    np.testing.assert_allclose(back, t, rtol=1e-12)
    assert run(TransmittanceToAbsorbance(), np.array([10.0, 1.0]), X[:2])[0] == 1.0


def test_log_and_inverse() -> None:
    np.testing.assert_allclose(
        run(Log10(), np.array([1.0, 10, 100, 1000])), [0, 1, 2, 3]
    )
    np.testing.assert_allclose(run(Inverse()), 1.0 / Y)
    assert run(Inverse(), np.array([-2.0, 4.0, 1.0, 1.0]))[0] == -0.5


@pytest.mark.parametrize("bad", [0.0, -1.0, np.nan])
def test_non_positive_errors(bad: float) -> None:
    y = np.array([1.0, bad, 3.0, 4.0])
    for t in (TransmittanceToAbsorbance(), Log10()):
        with pytest.raises(NonPositiveValue, match="index 1"):
            run(t, y)


def test_other_value_errors() -> None:
    with pytest.raises(DivisionByZero, match="index 1"):
        run(Inverse(), np.array([1.0, 0.0, 1.0, 1.0]))
    with pytest.raises(InvalidTransform, match="not finite"):
        run(Inverse(), np.array([1e-320, 1.0, 1.0, 1.0]))
    with pytest.raises(InvalidTransform, match="not finite"):
        run(AbsorbanceToTransmittance(), np.array([-400.0, 0.0, 0.0, 0.0]))
    for y in (np.zeros(4), -Y):
        with pytest.raises(CannotNormalise, match="maximum"):
            run(NormaliseToMax(), y)
    with pytest.raises(CannotNormalise, match="outside"):
        run(NormaliseAtX(900.0, NM, Unit.NM))
    with pytest.raises(CannotNormalise, match="zero"):
        run(NormaliseAtX(300.0, NM, Unit.NM), np.array([1.0, 0.0, 1.0, 1.0]))


def test_parameter_validation() -> None:
    with pytest.raises(InvalidTransform):
        Level(float("nan"))
    with pytest.raises(InvalidTransform):
        NormaliseAtX(300.0, Quantity.ABSORBANCE, Unit.DIMENSIONLESS)
    with pytest.raises(InvalidTransform):
        NormaliseAtX(300.0, NM, Unit.EV)
    with pytest.raises(NonPositiveValue):
        NormaliseAtX(-1.0, NM, Unit.NM)


def test_result_quantities() -> None:
    tq, aq = Quantity.TRANSMITTANCE, Quantity.ABSORBANCE
    assert TransmittanceToAbsorbance().result_quantity(tq) is aq
    assert AbsorbanceToTransmittance().result_quantity(aq) is tq
    assert Level(1.0).result_quantity(aq) is aq
    assert NormaliseToMax().result_quantity(aq) is Quantity.NORMALISED_INTENSITY
    assert Log10().result_quantity(aq) == DerivedQuantity("log10", aq)
    assert Log10().result_quantity(aq) != Inverse().result_quantity(aq)
    assert Inverse().result_quantity(Log10().result_quantity(aq)) == DerivedQuantity(
        "inverse", DerivedQuantity("log10", aq)
    )
    with pytest.raises(InvalidTransform, match="transmittance"):
        TransmittanceToAbsorbance().result_quantity(aq)
    with pytest.raises(InvalidTransform, match="absorbance"):
        AbsorbanceToTransmittance().result_quantity(tq)


def test_composition_order_and_reversibility() -> None:
    t = np.array([80.0, 40.0, 20.0, 10.0])
    chain = (TransmittanceToAbsorbance(), Level(0.5), NormaliseToMax())
    y, q = apply_transforms(X, t, NM, Quantity.TRANSMITTANCE, chain)
    a = 2.0 - np.log10(t) - 0.5
    np.testing.assert_allclose(y, a / a.max())
    assert q is Quantity.NORMALISED_INTENSITY
    # Removing the last transform gives the previous curve; none gives the raw data.
    y2, q2 = apply_transforms(X, t, NM, Quantity.TRANSMITTANCE, chain[:2])
    np.testing.assert_allclose(y2, a)
    assert q2 is Quantity.ABSORBANCE
    y0, q0 = apply_transforms(X, t, NM, Quantity.TRANSMITTANCE, ())
    np.testing.assert_array_equal(y0, t)
    assert q0 is Quantity.TRANSMITTANCE
    # Order matters: leveling before or after normalising differs.
    swapped = (NormaliseToMax(), Level(0.1))
    s, _ = apply_transforms(X, Y, NM, Quantity.ABSORBANCE, swapped)
    r, _ = apply_transforms(X, Y, NM, Quantity.ABSORBANCE, swapped[::-1])
    assert not np.allclose(s, r)


def test_composition_errors_and_inputs_untouched() -> None:
    raw = Y.copy()
    with pytest.raises(InvalidTransform):
        apply_transforms(
            X, raw, NM, Quantity.ABSORBANCE, (TransmittanceToAbsorbance(),)
        )
    with pytest.raises(InvalidTransform):  # second step no longer sees transmittance
        apply_transforms(
            X,
            np.array([50.0, 40.0, 30.0, 20.0]),
            NM,
            Quantity.TRANSMITTANCE,
            (TransmittanceToAbsorbance(), TransmittanceToAbsorbance()),
        )
    with pytest.raises(NonPositiveValue):  # level pushes values below zero before log
        apply_transforms(X, raw, NM, Quantity.ABSORBANCE, (Level(0.5), Log10()))
    out, _ = apply_transforms(X, raw, NM, Quantity.ABSORBANCE, (Level(0.1),))
    out[0] = 99.0
    np.testing.assert_array_equal(raw, Y)
