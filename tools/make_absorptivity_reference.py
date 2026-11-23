# SPDX-License-Identifier: GPL-3.0-or-later
"""Write the qclab-utilities reference curves for T3.4 AC3.

Run once, from the repository root, with a local checkout of qclab-utilities:

    python tools/make_absorptivity_reference.py <path-to-qclab-utilities>

For each case it reads the corpus file with qclab's own parsers (an independent
reader), broadens with ``absspectra``/``irspectra`` core functions and writes
``tests/unit/data/absorptivity/<case>.csv``: a commented header with the widths in
cm⁻¹ and the qclab commit, then ``wavenumber_cm1,eps_l_mol_cm`` rows. The tests read
these files; they never need qclab-utilities.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "corpus" / "theoretical"
OUT = ROOT / "tests" / "unit" / "data" / "absorptivity"

# name, corpus file, shape, sigma (meV or cm-1), gamma (meV or cm-1)
UV_CASES = [
    ("3bands-gaussian", "synthetic-3bands.out", "gaussian", 250.0, 0.0),
    ("3bands-lorentzian", "synthetic-3bands.out", "lorentzian", 0.0, 100.0),
    ("3bands-voigt", "synthetic-3bands.out", "voigt", 150.0, 50.0),
    ("shoulder-gaussian", "synthetic-shoulder.out", "gaussian", 250.0, 0.0),
    ("wave-gaussian", "synthetic-wave.out", "gaussian", 250.0, 0.0),
    ("artificial-gaussian", "artificial.exspectrum", "gaussian", 250.0, 0.0),
]
IR_CASES = [
    ("imaginary-lorentzian-2", "imaginary-mode.vibspectrum", 2.0),
    ("imaginary-lorentzian-10", "imaginary-mode.vibspectrum", 10.0),
]
UV_RANGE_NM = (200.0, 800.0, 1.0)
IR_RANGE_CM1 = (400.0, 3600.0, 1.0)


def _write(name: str, header: list[str], grid: np.ndarray, eps: np.ndarray) -> None:
    order = np.argsort(grid)
    lines = [f"# {h}" for h in header]
    lines.append("wavenumber_cm1,eps_l_mol_cm")
    lines += [
        f"{x:.17g},{y:.17g}" for x, y in zip(grid[order], eps[order], strict=True)
    ]
    (OUT / f"{name}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(qclab: Path) -> None:
    sys.path.insert(0, str(qclab))
    from common.parsers import read_modes, read_transitions  # type: ignore[import-not-found]
    from utils.absspectra import core as abs_core  # type: ignore[import-not-found]
    from utils.irspectra import core as ir_core  # type: ignore[import-not-found]

    commit = subprocess.run(
        ["git", "-C", str(qclab), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, source, shape, sigma_mev, gamma_mev in UV_CASES:
        trans = read_transitions(str(CORPUS / source))
        _, grid = abs_core.build_grid(UV_RANGE_NM)
        sigma = abs_core.mev_to_cm1(sigma_mev)
        gamma = abs_core.mev_to_cm1(gamma_mev)
        eps = abs_core.broaden(shape, grid, trans.cm1, trans.fosc, sigma, gamma)
        header = [
            f"source={source}",
            "technique=UV-Vis",
            f"shape={shape}",
            f"sigma_cm1={sigma!r}",
            f"gamma_cm1={gamma!r}",
            f"qclab-utilities absspectra, commit {commit or 'unknown'}",
        ]
        _write(name, header, grid, eps)
    for name, source, gamma in IR_CASES:
        modes = read_modes(str(CORPUS / source))
        real, _ = ir_core.split_imaginary(modes)
        grid = ir_core.build_grid(IR_RANGE_CM1)
        areas = ir_core.mode_areas(modes.intensity[real])
        eps = ir_core.broaden(grid, modes.wavenumber[real], areas, gamma)
        header = [
            f"source={source}",
            "technique=IR",
            "shape=lorentzian",
            "sigma_cm1=0.0",
            f"gamma_cm1={gamma!r}",
            f"qclab-utilities irspectra, commit {commit or 'unknown'}",
        ]
        _write(name, header, grid, eps)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: make_absorptivity_reference.py <qclab-utilities>")
    main(Path(sys.argv[1]).resolve())
