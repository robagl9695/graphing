# SPDX-License-Identifier: GPL-3.0-or-later
"""T3.4 AC3: ε curves of the corpus files against qclab-utilities.

The reference curves in ``data/absorptivity/`` were written once by
``tools/make_absorptivity_reference.py`` with qclab's own parsers and its
``absspectra``/``irspectra`` broadening. qclab's f → ε constant (2.315115e8) differs
from the CODATA 2018 value used here by 1.02e-4 relative, so the UV-Vis references are
multiplied by the ratio of the two constants first (D-20261122-09). The IR constant
(100 / ln 10) is the same in both.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from graphing.core.broadening import broaden
from graphing.core.constants import INTEGRATED_ABSORPTIVITY_PER_F
from graphing.core.data import StickData
from graphing.core.io import load
from graphing.core.model import Broadening, LineShape
from graphing.core.spectrum import Origin, Technique
from graphing.core.transforms import (
    IRIntensityToAbsorptivity,
    LinesToAbsorptivity,
    OscillatorStrengthToAbsorptivity,
)
from graphing.core.units import Quantity, Unit

DATA = Path(__file__).parent / "data" / "absorptivity"
CORPUS = Path(__file__).parents[1] / "corpus" / "theoretical"

QCLAB_F_CONSTANT = 2.315115e8
AC3_RTOL = 1e-6

FORMATS = {
    ".out": "orca",
    ".exspectrum": "turbomole-exspectrum",
    ".vibspectrum": "turbomole-vibspectrum",
}
SHAPES = {
    "gaussian": LineShape.GAUSSIAN,
    "lorentzian": LineShape.LORENTZIAN,
    "voigt": LineShape.VOIGT,
}
GAUSSIAN_FWHM_PER_SIGMA = 2.0 * math.sqrt(2.0 * math.log(2.0))


def read_reference(path: Path) -> tuple[dict[str, str], np.ndarray, np.ndarray]:
    header: dict[str, str] = {}
    rows: list[tuple[float, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            if "=" in line:
                key, value = line[2:].split("=", 1)
                header[key] = value
        elif not line.startswith("wavenumber"):
            x, y = line.split(",")
            rows.append((float(x), float(y)))
    table = np.array(rows)
    return header, table[:, 0], table[:, 1]


def broadening_for(header: dict[str, str]) -> Broadening:
    shape = SHAPES[header["shape"]]
    sigma, gamma = float(header["sigma_cm1"]), float(header["gamma_cm1"])
    if shape is LineShape.GAUSSIAN:
        return Broadening(
            line_shape=shape, fwhm=sigma * GAUSSIAN_FWHM_PER_SIGMA, fwhm_unit=Unit.CM1
        )
    if shape is LineShape.LORENTZIAN:
        return Broadening(line_shape=shape, fwhm=2.0 * gamma, fwhm_unit=Unit.CM1)
    return Broadening(
        line_shape=shape,
        fwhm=sigma * GAUSSIAN_FWHM_PER_SIGMA,
        fwhm_unit=Unit.CM1,
        fwhm_lorentzian=2.0 * gamma,
    )


CASES = sorted(DATA.glob("*.csv"))


def test_every_case_is_present() -> None:
    assert len(CASES) == 8


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_ac3_matches_qclab(path: Path) -> None:
    header, grid, reference = read_reference(path)
    source = CORPUS / header["source"]
    technique = Technique.UV_VIS if header["technique"] == "UV-Vis" else Technique.IR
    (spectrum,) = load(source, technique, Origin.THEORETICAL, FORMATS[source.suffix])
    assert isinstance(spectrum.data, StickData)
    y = broaden(spectrum.data, broadening_for(header), grid).y
    transform: LinesToAbsorptivity
    if technique is Technique.UV_VIS:
        transform = OscillatorStrengthToAbsorptivity()
        expected = reference * (INTEGRATED_ABSORPTIVITY_PER_F / QCLAB_F_CONSTANT)
    else:
        transform = IRIntensityToAbsorptivity()
        expected = reference
    eps = transform.apply(grid, y, Quantity.WAVENUMBER)
    np.testing.assert_allclose(eps, expected, rtol=AC3_RTOL, atol=0.0)
