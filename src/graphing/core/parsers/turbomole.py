# SPDX-License-Identifier: GPL-3.0-or-later
"""Readers of Turbomole spectra: electronic excitations and IR.

Ported from ``qclab-utilities/common/parsers/turbomole.py`` and modernised.

* ``exspectrum``: two ``#`` header lines, then one row per state with the energy in four
  units and the oscillator strength in both gauges. :func:`parse_turbomole_exspectrum`.
* ``escf.out``: the verbose log of ``escf``, one paragraph per excited state at full
  precision. :func:`parse_turbomole_escf`. Its compact summary table is not used: it
  rounds the oscillator strengths to five decimals, which turns weak transitions into
  zeros.
* ``vibspectrum``: the ``$vibrational spectrum`` table, one row per mode.
  :func:`parse_turbomole_vibspectrum`.

Only the length representation of the oscillator strength is returned; the velocity one
and the rotatory strengths are not read (circular dichroism is deferred).

Nothing is dropped from the IR table: translations and rotations, IR-inactive modes and
imaginary frequencies are all returned, flagged, and the consumer chooses. A block ends
at its section end, and a line inside it that is not a valid row is an error
(:class:`~graphing.core.errors.MalformedBlock`), so a damaged row can never make the
result silently shorter.

Support is claimed only for families that have a real, publishable file in the public
corpus (CLAUDE.md section 8.3); see :data:`VERIFIED_FAMILIES`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from graphing.core.errors import MalformedBlock, MissingBlock, UnreadableFile
from graphing.core.readers.text import decode

#: Families with a real public corpus file that reads correctly. Empty until Rob
#: confirms such a file can be published; a test keeps it equal to the corpus.
VERIFIED_FAMILIES: frozenset[str] = frozenset()

_FAMILY = "7.x"
_VERSION = re.compile(r"TURBOMOLE\s+V(\d+(?:\.\d+)*)")
_ESCF_HEADER = re.compile(r"^\s*(\d+)\s+(singlet|triplet)\s+(\S+)\s+excitation\s*$")
_FLAGS = {"YES", "NO", "-"}
# Printed wavelengths and energies carry three decimals.
_ROUNDING = 0.0011


@dataclass(frozen=True)
class TurbomoleAbsorption:
    """Excited states of a Turbomole output, in file order.

    Attributes
    ----------
    energy_cm1
        Excitation energy of each state in cm-1.
    fosc
        Oscillator strength, length representation.
    wavelength_nm
        Wavelength in nm as the program printed it, or ``None`` if not printed.
    labels
        One label per state: ``"1 a"`` (exspectrum) or ``"1 singlet a"`` (escf.out).
    source
        ``"exspectrum"`` or ``"escf.out"``.
    version
        Turbomole version when the file says so (only ``escf.out`` does), else ``None``.
    warnings
        Things the caller should know, e.g. that the family is not verified.
    """

    energy_cm1: NDArray[np.float64]
    fosc: NDArray[np.float64]
    wavelength_nm: NDArray[np.float64] | None
    labels: tuple[str, ...]
    source: str
    version: str | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class TurbomoleIR:
    """Every mode of a ``vibspectrum``, in file order, with flags.

    Attributes
    ----------
    mode_index
        The program's mode numbers (the first ones are translations and rotations).
    symmetry
        Irreducible representation, or ``"-"`` when the program prints none.
    wavenumber_cm1, intensity_km_mol
        Frequency and IR intensity.
    ir_active, raman_active
        The ``IR`` and ``RAMAN`` selection columns (``YES``).
    imaginary
        True where the wave number is negative (an imaginary frequency).
    warnings
        As in :class:`TurbomoleAbsorption`.
    """

    mode_index: tuple[int, ...]
    symmetry: tuple[str, ...]
    wavenumber_cm1: NDArray[np.float64]
    intensity_km_mol: NDArray[np.float64]
    ir_active: NDArray[np.bool_]
    raman_active: NDArray[np.bool_]
    imaginary: NDArray[np.bool_]
    warnings: tuple[str, ...]


def read_turbomole_exspectrum(path: str | Path) -> TurbomoleAbsorption:
    """Read an ``exspectrum`` file; see :func:`parse_turbomole_exspectrum`."""
    text, source = _read(path)
    return parse_turbomole_exspectrum(text, source)


def read_turbomole_escf(path: str | Path) -> TurbomoleAbsorption:
    """Read an ``escf.out`` file; see :func:`parse_turbomole_escf`."""
    text, source = _read(path)
    return parse_turbomole_escf(text, source)


def read_turbomole_vibspectrum(path: str | Path) -> TurbomoleIR:
    """Read a ``vibspectrum`` file; see :func:`parse_turbomole_vibspectrum`."""
    text, source = _read(path)
    return parse_turbomole_vibspectrum(text, source)


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


def parse_turbomole_exspectrum(
    text: str, source: str = "exspectrum"
) -> TurbomoleAbsorption:
    """Parse a Turbomole ``exspectrum`` file.

    Raises
    ------
    MissingBlock
        The text has no ``#`` header naming the ``Exc.`` and ``Osc.(len)`` columns.
    MalformedBlock
        A row is not ``index symmetry`` followed by six numbers, a wavelength disagrees
        with its energy, or there are no rows.
    """
    lines = text.splitlines()
    header = " ".join(line.lower() for line in lines if line.strip().startswith("#"))
    if "exc." not in header or "osc.(len)" not in header:
        raise MissingBlock(
            f"{source} has no exspectrum header (a '#' line naming 'Exc.' and "
            "'Osc.(len)')."
        )
    energy, nm, fosc, labels = [], [], [], []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        row = _exspectrum_row(stripped)
        if row is None:
            raise MalformedBlock(
                f"Line {index + 1} of {source} is not a valid exspectrum row: "
                f"'{stripped[:60]}'."
            )
        label, numbers = row
        _check_consistent(numbers[2], numbers[3], index + 1, source)
        labels.append(label)
        energy.append(numbers[2])
        nm.append(numbers[3])
        fosc.append(numbers[5])
    if not energy:
        raise MalformedBlock(f"{source} has an exspectrum header but no rows.")
    return TurbomoleAbsorption(
        energy_cm1=np.array(energy, dtype=np.float64),
        fosc=np.array(fosc, dtype=np.float64),
        wavelength_nm=np.array(nm, dtype=np.float64),
        labels=tuple(labels),
        source="exspectrum",
        version=None,
        warnings=_warnings(),
    )


def _exspectrum_row(stripped: str) -> tuple[str, list[float]] | None:
    tokens = stripped.split()
    if len(tokens) != 8 or not tokens[0].isdigit():
        return None
    try:
        numbers = [float(token) for token in tokens[2:]]
    except ValueError:
        return None
    # numbers: Eh, eV, cm-1, nm, Osc.(vel), Osc.(len)
    return f"{tokens[0]} {tokens[1]}", numbers


def parse_turbomole_escf(text: str, source: str = "escf.out") -> TurbomoleAbsorption:
    """Parse the per-state paragraphs of an ``escf.out`` log.

    Each state is a paragraph that starts with
    ``<n> singlet|triplet <irrep> excitation``; from it the energy in cm-1 and the
    oscillator strength (length representation, under ``Oscillator strength:``, not the
    one under ``Rotatory strength:``) are read.

    Raises
    ------
    MissingBlock
        The log has no excitation paragraphs.
    MalformedBlock
        A paragraph lacks its energy or its oscillator strength, or a number is broken.
    """
    lines = text.splitlines()
    states = _escf_paragraphs(lines, source)
    if not states:
        raise MissingBlock(
            f"{source} has no '<n> singlet|triplet <irrep> excitation' paragraph."
        )
    nm_values = [state["nm"] for state in states]
    return TurbomoleAbsorption(
        energy_cm1=np.array([state["cm1"] for state in states], dtype=np.float64),
        fosc=np.array([state["fosc"] for state in states], dtype=np.float64),
        wavelength_nm=(
            None
            if any(v is None for v in nm_values)
            else np.array(nm_values, dtype=np.float64)
        ),
        labels=tuple(str(state["label"]) for state in states),
        source="escf.out",
        version=_version(lines),
        warnings=_warnings(),
    )


def _escf_paragraphs(lines: list[str], source: str) -> list[dict[str, object]]:
    states: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    in_oscillator = False

    def close() -> None:
        if current is None:
            return
        for key, name in (
            ("cm1", "energy / cm^(-1)"),
            ("fosc", "length representation"),
        ):
            if current.get(key) is None:
                raise MalformedBlock(
                    f"The paragraph of state '{current['label']}' (line "
                    f"{current['line']}) of {source} has no '{name}'."
                )
        states.append(current)

    for index, line in enumerate(lines):
        match = _ESCF_HEADER.match(line)
        if match:
            close()
            number, spin, irrep = match.groups()
            current = {
                "label": f"{number} {spin} {irrep}",
                "line": index + 1,
                "cm1": None,
                "nm": None,
                "fosc": None,
            }
            in_oscillator = False
            continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped.startswith("Excitation energy / cm^(-1):"):
            current["cm1"] = _number(stripped.split(":", 1)[1], index, source)
        elif stripped.startswith("Excitation energy / nm:"):
            current["nm"] = _number(stripped.split(":", 1)[1], index, source)
        elif stripped.startswith("Oscillator strength:"):
            in_oscillator = True
        elif stripped.startswith("Rotatory strength:"):
            in_oscillator = False
        elif in_oscillator and stripped.startswith("length representation:"):
            current["fosc"] = _number(stripped.split(":", 1)[1], index, source)
            in_oscillator = False
    close()
    return states


def _number(text: str, index: int, source: str) -> float:
    try:
        return float(text.strip().replace("D", "E").replace("d", "e"))
    except ValueError:
        raise MalformedBlock(
            f"Line {index + 1} of {source} has a number that cannot be read: "
            f"'{text.strip()}'."
        ) from None


def parse_turbomole_vibspectrum(text: str, source: str = "vibspectrum") -> TurbomoleIR:
    """Parse a Turbomole ``vibspectrum`` file; every mode is returned, flagged.

    Raises
    ------
    MissingBlock
        The text has no ``$vibrational spectrum`` section.
    MalformedBlock
        A row is broken, the section has no rows, or it has no ``$end`` (the file looks
        truncated).
    """
    lines = text.splitlines()
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if line.strip().startswith("$vibrational spectrum")
        ),
        None,
    )
    if start is None:
        raise MissingBlock(f"No '$vibrational spectrum' section was found in {source}.")

    rows: list[tuple[int, str, float, float, str, str]] = []
    ended = False
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("$"):
            ended = stripped.startswith("$end")
            break
        row = _vib_row(stripped)
        if row is None:
            raise MalformedBlock(
                f"Line {index + 1} of {source} is inside '$vibrational spectrum' but "
                f"is not a valid mode row: '{stripped[:60]}'."
            )
        rows.append(row)
    if not ended:
        raise MalformedBlock(
            f"The '$vibrational spectrum' section of {source} has no '$end'; the "
            "file looks truncated."
        )
    if not rows:
        raise MalformedBlock(
            f"The '$vibrational spectrum' section of {source} has no rows."
        )

    wavenumber = np.array([row[2] for row in rows], dtype=np.float64)
    return TurbomoleIR(
        mode_index=tuple(row[0] for row in rows),
        symmetry=tuple(row[1] for row in rows),
        wavenumber_cm1=wavenumber,
        intensity_km_mol=np.array([row[3] for row in rows], dtype=np.float64),
        ir_active=np.array([row[4] == "YES" for row in rows], dtype=np.bool_),
        raman_active=np.array([row[5] == "YES" for row in rows], dtype=np.bool_),
        imaginary=wavenumber < 0,
        warnings=_warnings(),
    )


def _vib_row(stripped: str) -> tuple[int, str, float, float, str, str] | None:
    tokens = stripped.split()
    if len(tokens) not in (5, 6) or not tokens[0].isdigit():
        return None
    if tokens[-2] not in _FLAGS or tokens[-1] not in _FLAGS:
        return None
    try:
        wavenumber = float(tokens[-4])
        intensity = float(tokens[-3])
    except ValueError:
        return None
    symmetry = tokens[1] if len(tokens) == 6 else "-"
    return int(tokens[0]), symmetry, wavenumber, intensity, tokens[-2], tokens[-1]


def _check_consistent(cm1: float, nm: float, line_number: int, source: str) -> None:
    """The wavelength must agree with the energy, to the printed precision."""
    if cm1 <= 0:
        raise MalformedBlock(
            f"Line {line_number} of {source}: energy {cm1} cm-1 is not positive."
        )
    tolerance = _ROUNDING + 1e7 / cm1**2 * _ROUNDING
    if abs(1e7 / cm1 - nm) > tolerance:
        raise MalformedBlock(
            f"Line {line_number} of {source}: {nm} nm does not match {cm1} cm-1 "
            f"(expected {1e7 / cm1:.3f} nm); the columns were probably misread."
        )


def _version(lines: list[str]) -> str | None:
    for line in lines[:30]:
        match = _VERSION.search(line)
        if match:
            return match.group(1)
    return None


def _warnings() -> tuple[str, ...]:
    if _FAMILY in VERIFIED_FAMILIES:
        return ()
    return (f"Turbomole {_FAMILY} is not verified against a real corpus file yet.",)
