# SPDX-License-Identifier: GPL-3.0-or-later
"""Readers of the spectrum blocks of ORCA outputs: UV-Vis absorption and IR.

Ported from ``qclab-utilities/common/parsers/orca.py`` and modernised.

The absorption block is found by an *exact* match of its title, never a substring:
ORCA also prints ``ABSORPTION SPECTRUM VIA TRANSITION VELOCITY DIPOLE MOMENTS`` and
``CD SPECTRUM`` blocks (the 6.x CD titles even contain ``VIA TRANSITION ELECTRIC DIPOLE
MOMENTS``). Those blocks are ignored; circular dichroism is deferred to a later version.

Two layouts of the absorption rows are recognised, told apart by the number of leading
non-numeric tokens and of numeric fields, not by fixed columns:

======  ====  =======  ===============================================
Family  Lead  Numbers  Numeric fields
======  ====  =======  ===============================================
4.x     0     8        state, cm-1, nm, fosc, T2, TX, TY, TZ
6.x     1+    8        eV, cm-1, nm, fosc(D2), D2, DX, DY, DZ
======  ====  =======  ===============================================

In 6.x the leading label is a transition such as ``0-2A  ->  1-4A`` (three tokens).

Support is claimed only for families that have a real, publishable file in the public
corpus (CLAUDE.md section 8.3). Until then every result carries a warning saying so;
see :data:`VERIFIED_FAMILIES`.

A block ends at its first blank line. Any line inside it that is not a data row is an
error (:class:`~graphing.core.errors.MalformedBlock`), so a damaged row can never make
the result silently shorter.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from graphing.core.errors import MalformedBlock, MissingBlock, UnreadableFile
from graphing.core.readers.text import decode

ABSORPTION_TITLE = "ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS"
IR_TITLE = "IR SPECTRUM"

#: Families with a real public corpus file that reads correctly. Empty until Rob
#: confirms such a file can be published; a test keeps it equal to the corpus.
VERIFIED_FAMILIES: frozenset[str] = frozenset()

_SEPARATOR = set("-= ")
_VERSION = re.compile(r"Program Version\s+(\d+)\.(\d+)\.(\d+)")
_ABSORPTION_FIELDS = 8
_Row = tuple[Any, ...]  # a parsed row: see _absorption_row and _ir_row
# Printed wavelengths carry one decimal and energies at most one: allow their rounding.
_NM_ROUNDING = 0.051
_CM1_ROUNDING = 0.051


@dataclass(frozen=True)
class OrcaAbsorption:
    """Transitions of an ORCA absorption block, in file order.

    Attributes
    ----------
    energy_cm1, wavelength_nm, fosc
        One value per transition: energy in cm-1, wavelength in nm, oscillator strength.
    layout
        ``"4.x"`` or ``"6.x"``, from the shape of the rows.
    version
        The ``Program Version`` text of the output (``"6.0.1"``), or ``None``.
    warnings
        Things the caller should know, e.g. that the family is not verified.
    """

    energy_cm1: NDArray[np.float64]
    wavelength_nm: NDArray[np.float64]
    fosc: NDArray[np.float64]
    layout: str
    version: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OrcaIR:
    """Vibrational modes of an ORCA ``IR SPECTRUM`` block, in file order.

    Attributes
    ----------
    mode_index
        ORCA's mode numbers (translations and rotations are not listed).
    wavenumber_cm1, intensity_km_mol
        Frequency and IR intensity; the intensity is what broadening uses.
    eps_orca
        ORCA's own molar absorptivity column, kept only as a cross-check.
    version, warnings
        As in :class:`OrcaAbsorption`.
    """

    mode_index: tuple[int, ...]
    wavenumber_cm1: NDArray[np.float64]
    intensity_km_mol: NDArray[np.float64]
    eps_orca: NDArray[np.float64]
    version: str | None
    warnings: tuple[str, ...]


def read_orca_absorption(path: str | Path) -> OrcaAbsorption:
    """Read the absorption block of an ORCA file; see :func:`parse_orca_absorption`."""
    text, source = _read(path)
    return parse_orca_absorption(text, source)


def read_orca_ir(path: str | Path) -> OrcaIR:
    """Read the IR block of an ORCA output file. See :func:`parse_orca_ir`."""
    text, source = _read(path)
    return parse_orca_ir(text, source)


def _read(path: str | Path) -> tuple[str, str]:
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise UnreadableFile(
            f"Cannot read '{path}': {error.strerror or error}."
        ) from error
    text, _ = decode(raw, None, str(path))
    return text, str(path)


def parse_orca_absorption(text: str, source: str = "ORCA output") -> OrcaAbsorption:
    """Parse the electric-dipole absorption block of a full ORCA output.

    Parameters
    ----------
    text
        The complete output.
    source
        Name used in error messages.

    Returns
    -------
    OrcaAbsorption
        The transitions in file order.

    Raises
    ------
    MissingBlock
        The output has no ``ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS``
        block.
    MalformedBlock
        A row is broken, rows differ in shape, the layout is not recognised, or a
        wavelength disagrees with its energy.
    """
    lines = text.splitlines()
    start = _find_title(lines, ABSORPTION_TITLE, source)
    rows = _block_rows(lines, start, _absorption_row, source, ABSORPTION_TITLE)

    shapes = {(row[0], len(row[1])) for _, row in rows}
    if len(shapes) != 1:
        raise MalformedBlock(
            f"The rows of the absorption block of {source} differ in shape."
        )
    lead, count = next(iter(shapes))
    layout = "4.x" if lead == 0 else "6.x"
    if count != _ABSORPTION_FIELDS:  # pragma: no cover - _absorption_row enforces it
        raise MalformedBlock(f"Unrecognised absorption layout in {source}.")

    energy = np.array([row[1][1] for _, row in rows], dtype=np.float64)
    wavelength = np.array([row[1][2] for _, row in rows], dtype=np.float64)
    fosc = np.array([row[1][3] for _, row in rows], dtype=np.float64)
    for (line_number, _), cm1, nm in zip(rows, energy, wavelength, strict=True):
        _check_consistent(cm1, nm, line_number, source)

    version = _version(lines)
    return OrcaAbsorption(
        energy_cm1=energy,
        wavelength_nm=wavelength,
        fosc=fosc,
        layout=layout,
        version=version,
        warnings=_warnings(layout, version, expected_major=4 if layout == "4.x" else 6),
    )


def parse_orca_ir(text: str, source: str = "ORCA output") -> OrcaIR:
    """Parse the ``IR SPECTRUM`` block (ORCA 6.x) of a full ORCA output.

    Raises
    ------
    MissingBlock
        The output has no ``IR SPECTRUM`` block.
    MalformedBlock
        A row of the block is broken.
    """
    lines = text.splitlines()
    start = _find_title(lines, IR_TITLE, source)
    rows = _block_rows(lines, start, _ir_row, source, IR_TITLE)
    version = _version(lines)
    return OrcaIR(
        mode_index=tuple(row[0] for _, row in rows),
        wavenumber_cm1=np.array([row[1] for _, row in rows], dtype=np.float64),
        intensity_km_mol=np.array([row[3] for _, row in rows], dtype=np.float64),
        eps_orca=np.array([row[2] for _, row in rows], dtype=np.float64),
        version=version,
        warnings=_warnings("6.x", version, expected_major=6),
    )


def _find_title(lines: list[str], title: str, source: str) -> int:
    for index, line in enumerate(lines):
        if line.strip() == title:
            return index
    raise MissingBlock(f"No '{title}' block was found in {source}.")


def _block_rows(
    lines: list[str],
    start: int,
    parse_row: Callable[[str], _Row | None],
    source: str,
    title: str,
) -> list[tuple[int, _Row]]:
    """Collect ``(line number, row)`` after a title, up to the first blank line.

    Before the first row, lines without any number (separators, column titles) are
    skipped. From the first row on, every non-blank line must be a valid row.
    """
    rows: list[tuple[int, _Row]] = []
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if not stripped:
            if rows:
                break
            continue
        parsed = parse_row(lines[index])
        if parsed is not None:
            rows.append((index + 1, parsed))
            continue
        if rows or _has_number(stripped):
            raise MalformedBlock(
                f"Line {index + 1} of {source} is inside the '{title}' block but is "
                f"not a valid row: '{stripped[:60]}'."
            )
    if not rows:
        raise MalformedBlock(f"The '{title}' block of {source} has no rows.")
    return rows


def _has_number(text: str) -> bool:
    """Whether any whitespace-separated token of ``text`` is a plain number."""
    for token in text.split():
        try:
            float(token)
        except ValueError:
            continue
        return True
    return False


def _absorption_row(line: str) -> tuple[int, list[float]] | None:
    tokens = line.split()
    lead = 0
    for token in tokens:
        try:
            float(token)
            break
        except ValueError:
            lead += 1
    try:
        numbers = [float(token) for token in tokens[lead:]]
    except ValueError:
        return None
    if len(numbers) != _ABSORPTION_FIELDS:
        return None
    return lead, numbers


def _ir_row(line: str) -> tuple[int, float, float, float] | None:
    tokens = line.split()
    if len(tokens) < 4 or not tokens[0].endswith(":") or not tokens[0][:-1].isdigit():
        return None
    try:
        frequency, eps, intensity = (float(token) for token in tokens[1:4])
    except ValueError:
        return None
    return int(tokens[0][:-1]), frequency, eps, intensity


def _check_consistent(cm1: float, nm: float, line_number: int, source: str) -> None:
    """The wavelength column must agree with the energy column, to printed precision."""
    if cm1 <= 0:
        raise MalformedBlock(
            f"Line {line_number} of {source}: energy {cm1} cm-1 is not positive."
        )
    tolerance = _NM_ROUNDING + 1e7 / cm1**2 * _CM1_ROUNDING
    if abs(1e7 / cm1 - nm) > tolerance:
        raise MalformedBlock(
            f"Line {line_number} of {source}: {nm} nm does not match {cm1} cm-1 "
            f"(expected {1e7 / cm1:.1f} nm); the columns were probably misread."
        )


def _version(lines: list[str]) -> str | None:
    for line in lines:
        match = _VERSION.search(line)
        if match:
            return ".".join(match.groups())
    return None


def _warnings(layout: str, version: str | None, expected_major: int) -> tuple[str, ...]:
    warnings = []
    if layout not in VERIFIED_FAMILIES:
        warnings.append(
            f"ORCA {layout} is not verified against a real corpus file yet."
        )
    if version is not None and int(version.split(".")[0]) != expected_major:
        warnings.append(
            f"The output says version {version}, but the block has the {layout} layout."
        )
    return tuple(warnings)
