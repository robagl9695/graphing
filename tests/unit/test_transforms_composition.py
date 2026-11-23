# SPDX-License-Identifier: GPL-3.0-or-later
"""Order and domain tests for composed y transforms (extra tests for T1.4).

The exhaustive tests compare ``apply_transforms`` with a reference written here with
plain NumPy: for every chain it says either the expected values and quantity, or the
exact named error. The two must agree on all chains of one to three transforms.
"""

import itertools
from typing import Any

import numpy as np
import pytest

from graphing.core.errors import (
    CannotNormalise,
    DivisionByZero,
    GraphingError,
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
PERCENT_T = np.array([80.0, 40.0, 20.0, 10.0])

TRANS, ABS, INTENSITY = (
    Quantity.TRANSMITTANCE,
    Quantity.ABSORBANCE,
    Quantity.INTENSITY,
)
ALL: tuple[YTransform, ...] = (
    TransmittanceToAbsorbance(),
    AbsorbanceToTransmittance(),
    Log10(),
    Inverse(),
    Level(0.1),
    NormaliseToMax(),
    NormaliseAtX(300.0, NM, Unit.NM),
)
STARTS = [(TRANS, PERCENT_T), (ABS, Y), (INTENSITY, Y)]
CHAINS = [c for n in (1, 2, 3) for c in itertools.product(ALL, repeat=n)]


def run(chain: Any, y: Any, q: Quantity) -> Any:
    return apply_transforms(X, y, NM, q, chain)


# --- hand-calculated order tests --------------------------------------------------


def test_swapping_level_and_normalise_gives_the_expected_values() -> None:
    level_first, _ = run((Level(0.1), NormaliseToMax()), Y, ABS)
    # (Y - 0.1) / 0.7
    np.testing.assert_allclose(level_first, [1 / 7, 1.0, 4 / 7, 0.0], atol=1e-15)
    normalise_first, _ = run((NormaliseToMax(), Level(0.1)), Y, ABS)
    # Y / 0.8 - 0.1
    np.testing.assert_allclose(normalise_first, [0.15, 0.9, 0.525, 0.025], atol=1e-15)


def test_reversing_a_valid_chain_can_make_it_fail() -> None:
    ok, q = run((TransmittanceToAbsorbance(), NormaliseToMax()), PERCENT_T, TRANS)
    assert q is Quantity.NORMALISED_INTENSITY
    assert ok.max() == 1.0
    with pytest.raises(InvalidTransform, match="transmittance"):
        run((NormaliseToMax(), TransmittanceToAbsorbance()), PERCENT_T, TRANS)


def test_level_before_log_fails_but_log_before_level_works() -> None:
    out, q = run((Log10(), Level(0.5)), Y, ABS)
    np.testing.assert_allclose(out, np.log10(Y) - 0.5)
    assert q == DerivedQuantity("log10", ABS)
    with pytest.raises(NonPositiveValue, match="index 0"):
        run((Level(0.5), Log10()), Y, ABS)


# --- reference implementation -----------------------------------------------------


def _fail(error: type[GraphingError]) -> tuple[str, type[GraphingError]]:
    return ("error", error)


def reference(start_q: Any, y0: Any, chain: Any) -> Any:
    """Return ('ok', y, quantity) or ('error', ErrorClass) for a chain."""
    y, q = np.array(y0, dtype=float), start_q
    for t in chain:
        if isinstance(t, TransmittanceToAbsorbance):
            if q is not TRANS:
                return _fail(InvalidTransform)
            if not np.all(y > 0):
                return _fail(NonPositiveValue)
            y, q = 2.0 - np.log10(y), ABS
        elif isinstance(t, AbsorbanceToTransmittance):
            if q is not ABS:
                return _fail(InvalidTransform)
            with np.errstate(over="ignore"):
                y, q = 10.0 ** (2.0 - y), TRANS
            if not np.all(np.isfinite(y)):
                return _fail(InvalidTransform)
        elif isinstance(t, Log10):
            if not np.all(y > 0):
                return _fail(NonPositiveValue)
            y, q = np.log10(y), DerivedQuantity("log10", q)
        elif isinstance(t, Inverse):
            if np.any(y == 0):
                return _fail(DivisionByZero)
            with np.errstate(over="ignore"):
                y, q = 1.0 / y, DerivedQuantity("inverse", q)
            if not np.all(np.isfinite(y)):
                return _fail(InvalidTransform)
        elif isinstance(t, Level):
            y = y - t.constant
        elif isinstance(t, NormaliseToMax):
            if not y.max() > 0:
                return _fail(CannotNormalise)
            y, q = y / y.max(), Quantity.NORMALISED_INTENSITY
        elif isinstance(t, NormaliseAtX):
            ref = float(np.interp(300.0, X, y))
            if ref == 0.0:
                return _fail(CannotNormalise)
            y, q = y / ref, Quantity.NORMALISED_INTENSITY
    return ("ok", y, q)


def outcome(chain: Any, y: Any, q: Quantity) -> Any:
    """What the real code does, in the same shape as ``reference``."""
    try:
        out, quantity = run(chain, y, q)
    except GraphingError as err:
        return ("error", type(err))
    return ("ok", out, quantity)


def same(a: Any, b: Any) -> bool:
    if a[0] != b[0]:
        return False
    if a[0] == "error":
        return bool(a[1] is b[1])
    return a[2] == b[2] and np.allclose(
        a[1], b[1], rtol=1e-12, atol=0.0, equal_nan=False
    )


# --- exhaustive tests -------------------------------------------------------------


@pytest.mark.parametrize(("start_q", "y"), STARTS, ids=["T", "A", "I"])
def test_every_chain_matches_the_reference(start_q: Quantity, y: Any) -> None:
    """Valid chains give the reference values; invalid ones raise the exact error."""
    for chain in CHAINS:
        got, want = outcome(chain, y, start_q), reference(start_q, y, chain)
        names = " > ".join(t.label for t in chain)
        assert same(got, want), (
            f"chain {names!r} from {start_q.value}: {got[:2]} vs {want[:2]}"
        )
        if got[0] == "ok":
            assert np.all(np.isfinite(got[1])), (
                f"chain {names!r} gave non-finite values"
            )


def test_both_outcomes_are_really_exercised() -> None:
    """Guard against a vacuous test: the chains include many valid and many failing."""
    results = [reference(q, y, c)[0] for q, y in STARTS for c in CHAINS]
    assert results.count("ok") > 300
    assert results.count("error") > 300


@pytest.mark.parametrize(("start_q", "y"), STARTS, ids=["T", "A", "I"])
def test_composition_of_compositions(start_q: Quantity, y: Any) -> None:
    """Applying a chain equals applying its head, then its tail on the result."""
    for chain in (c for c in CHAINS if len(c) == 3):
        whole = outcome(chain, y, start_q)
        for cut in (1, 2):
            head, tail = chain[:cut], chain[cut:]
            first = outcome(head, y, start_q)
            if first[0] == "error":
                staged = first
            else:
                staged = outcome(tail, first[1], first[2])
            assert same(whole, staged), (
                f"split at {cut} of {[t.label for t in chain]} from {start_q.value}"
            )
