# SPDX-License-Identifier: GPL-3.0-or-later
"""The single entry point for loading files (T2.7).

:func:`load` takes a path and what the user declared (technique and origin) and
dispatches to the registered readers. The app never guesses from content:

* A table (text or spreadsheet) is read as the user declared. Declared experimental,
  it becomes curves; declared theoretical, it becomes sticks, one per row in file
  order. A wrong declaration is not detected, warned about or corrected (CLAUDE §6.3);
  it simply gives the odd plot the declaration implies.
* A program output is always theoretical, so the declared origin is not used.
  Its format is named by the caller, because ``.out`` or a bare ``escf.out`` does not
  say which program wrote it.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from graphing.core.constants import NM_TO_CM1
from graphing.core.data import StickData
from graphing.core.errors import (
    InvalidData,
    InvalidMapping,
    NonNumericCells,
    UnknownFormat,
)
from graphing.core.parsers.orca import read_orca_absorption, read_orca_ir
from graphing.core.parsers.turbomole import (
    TurbomoleAbsorption,
    read_turbomole_escf,
    read_turbomole_exspectrum,
    read_turbomole_vibspectrum,
)
from graphing.core.readers.mapping import ColumnMapping, build_spectra, suggest_mapping
from graphing.core.readers.sheet import SUPPORTED_SUFFIXES as SHEET_SUFFIXES
from graphing.core.readers.sheet import read_sheet
from graphing.core.readers.text import ReadSettings, Table, read_text
from graphing.core.spectrum import Origin, Spectrum, Technique
from graphing.core.units import DEFAULT_UNIT, Quantity, Unit

Array = NDArray[np.float64]


@dataclass(frozen=True, kw_only=True)
class LoadOptions:
    """Optional choices for loading a table.

    Attributes
    ----------
    settings
        Format settings of a text file or sheet (``None`` fields are detected).
    sheet
        Sheet name or position of a spreadsheet; ``None`` = first with numbers.
    mapping
        Confirmed column choices. Its technique and origin are replaced by the
        declared ones. ``None`` = use the suggestion from the column names.
    """

    settings: ReadSettings | None = None
    sheet: str | int | None = None
    mapping: ColumnMapping | None = None


@dataclass(frozen=True)
class FileFormat:
    """A registered file format.

    Attributes
    ----------
    id
        Name used as ``format_id`` in :func:`load`.
    label
        Short description for the interface.
    suffixes
        File suffixes that select this format when no ``format_id`` is given;
        empty for program outputs, which must always be named.
    theoretical_only
        The format holds program output, so the origin is always theoretical.
    """

    id: str
    label: str
    suffixes: tuple[str, ...]
    theoretical_only: bool
    reader: Callable[[Path, Technique, Origin, LoadOptions], list[Spectrum]]


def load(
    path: str | Path,
    technique: Technique,
    origin: Origin,
    format_id: str | None = None,
    options: LoadOptions | None = None,
) -> list[Spectrum]:
    """Load the spectra of a file.

    Parameters
    ----------
    path
        File to read.
    technique, origin
        Declared by the user; used as given.
    format_id
        One of :func:`supported_formats`. May be omitted for tables, whose format
        follows from the file suffix.
    options
        Table options (settings, sheet, column mapping).

    Returns
    -------
    list of Spectrum
        One per y column of a table, or one per program block.

    Raises
    ------
    UnknownFormat
        ``format_id`` is not registered, or it is missing and the suffix is not
        that of a table.
    GraphingError
        Any error of the chosen reader, unchanged.
    """
    path = Path(path)
    fmt = _choose(path, format_id)
    return fmt.reader(path, technique, origin, options or LoadOptions())


def supported_formats() -> list[FileFormat]:
    """Return the registered formats, generated from the registry."""
    return list(_REGISTRY.values())


def _choose(path: Path, format_id: str | None) -> FileFormat:
    if format_id is not None:
        if format_id not in _REGISTRY:
            known = ", ".join(_REGISTRY)
            raise UnknownFormat(
                f"Unknown format {format_id!r}; known formats: {known}."
            )
        return _REGISTRY[format_id]
    suffix = path.suffix.lower()
    for fmt in _REGISTRY.values():
        if suffix in fmt.suffixes:
            return fmt
    raise UnknownFormat(
        f"Cannot choose a format for '{path.name}' from its suffix {suffix!r}. "
        "Name the format: program outputs always need it."
    )


# --- tables ---------------------------------------------------------------------


def _load_text(
    path: Path, technique: Technique, origin: Origin, options: LoadOptions
) -> list[Spectrum]:
    table = read_text(path, options.settings)
    return _from_table(table, path, technique, origin, options)


def _load_sheet(
    path: Path, technique: Technique, origin: Origin, options: LoadOptions
) -> list[Spectrum]:
    table = read_sheet(path, options.sheet, options.settings)
    return _from_table(table, path, technique, origin, options)


def _from_table(
    table: Table, path: Path, technique: Technique, origin: Origin, options: LoadOptions
) -> list[Spectrum]:
    if options.mapping is not None:
        mapping = dataclasses.replace(
            options.mapping, technique=technique, origin=origin
        )
    else:
        mapping = suggest_mapping(table).to_mapping(technique, origin)
    if origin is Origin.EXPERIMENTAL:
        return build_spectra(table, mapping, path.name)
    return _table_sticks(table, mapping, path.name)


def _table_sticks(table: Table, mapping: ColumnMapping, source: str) -> list[Spectrum]:
    """Theoretical table: every row is a line, in file order, repeats allowed."""
    ncols = table.data.shape[1]
    chosen = (mapping.x_column, *mapping.y_columns)
    if not mapping.y_columns:
        raise InvalidMapping("Choose at least one y column.")
    for column in chosen:
        if not 0 <= column < ncols:
            raise InvalidMapping(
                f"Column {column + 1} does not exist; the table has {ncols} columns."
            )
    if len(set(chosen)) != len(chosen):
        raise InvalidMapping("A column cannot be used twice (as x and y, or as two y).")
    for column in chosen:
        bad = np.flatnonzero(~np.isfinite(table.data[:, column]))
        if bad.size:
            raise NonNumericCells(
                f"Column {column + 1} in {source} has values that are not numbers "
                f"at row {int(bad[0]) + 1} of the numeric block."
            )
    names = table.columns
    spectra = []
    for column in mapping.y_columns:
        name = (
            names[column].strip()
            if names is not None and names[column].strip()
            else f"Column {column + 1}"
        )
        metadata = {"column": str(column + 1), "source": source}
        if table.preamble:
            metadata["preamble"] = "\n".join(table.preamble)
        data = StickData(
            x=table.data[:, mapping.x_column],
            y=table.data[:, column],
            x_quantity=mapping.x_quantity,
            x_unit=mapping.x_unit,
            y_quantity=mapping.y_quantity,
            y_unit=DEFAULT_UNIT[mapping.y_quantity],
        )
        spectra.append(
            Spectrum(
                name=name,
                data=data,
                metadata=metadata,
                technique=mapping.technique,
                origin=Origin.THEORETICAL,
            )
        )
    return spectra


# --- program outputs ------------------------------------------------------------


def _sticks(
    path: Path,
    technique: Technique,
    *,
    program: str,
    format_id: str,
    version: str | None,
    warnings: tuple[str, ...],
    x: Array,
    y: Array,
    ultraviolet: bool,
    labels: tuple[str, ...],
    extra: dict[str, str] | None = None,
) -> Spectrum:
    if ultraviolet:
        # Wavelength in nm, file order kept (convert_x would sort); Rob, S015.
        if not np.all(x > 0):
            raise InvalidData(
                f"{path.name}: a transition has zero or negative energy, so it has "
                "no wavelength"
            )
        data = StickData(
            x=NM_TO_CM1 / x,
            y=y,
            x_quantity=Quantity.WAVELENGTH,
            x_unit=Unit.NM,
            y_quantity=Quantity.OSCILLATOR_STRENGTH,
            y_unit=Unit.DIMENSIONLESS,
            labels=labels,
        )
    else:
        data = StickData(
            x=x,
            y=y,
            x_quantity=Quantity.WAVENUMBER,
            x_unit=Unit.CM1,
            y_quantity=Quantity.IR_INTENSITY,
            y_unit=Unit.KM_MOL,
            labels=labels,
        )
    metadata = {"program": program, "format": format_id, "source": path.name}
    if version:
        metadata["version"] = version
    if warnings:
        metadata["warnings"] = "\n".join(warnings)
    metadata.update(extra or {})
    return Spectrum(
        name=path.stem,
        data=data,
        metadata=metadata,
        technique=technique,
        origin=Origin.THEORETICAL,
    )


def _load_orca(
    path: Path, technique: Technique, origin: Origin, options: LoadOptions
) -> list[Spectrum]:
    if technique is Technique.IR:
        ir = read_orca_ir(path)
        return [
            _sticks(
                path,
                technique,
                program="ORCA",
                format_id="orca",
                version=ir.version,
                warnings=ir.warnings,
                x=ir.wavenumber_cm1,
                y=ir.intensity_km_mol,
                ultraviolet=False,
                labels=tuple(str(i) for i in ir.mode_index),
            )
        ]
    absorption = read_orca_absorption(path)
    return [
        _sticks(
            path,
            technique,
            program="ORCA",
            format_id="orca",
            version=absorption.version,
            warnings=absorption.warnings,
            x=absorption.energy_cm1,
            y=absorption.fosc,
            ultraviolet=True,
            labels=tuple(str(i) for i in range(1, absorption.energy_cm1.size + 1)),
            extra={"layout": absorption.layout},
        )
    ]


def _turbomole_absorption(
    reader: Callable[[Path], TurbomoleAbsorption], format_id: str
) -> Callable[[Path, Technique, Origin, LoadOptions], list[Spectrum]]:
    def load_it(
        path: Path, technique: Technique, origin: Origin, options: LoadOptions
    ) -> list[Spectrum]:
        result = reader(path)
        return [
            _sticks(
                path,
                technique,
                program="Turbomole",
                format_id=format_id,
                version=result.version,
                warnings=result.warnings,
                x=result.energy_cm1,
                y=result.fosc,
                ultraviolet=True,
                labels=result.labels,
            )
        ]

    return load_it


def _load_turbomole_ir(
    path: Path, technique: Technique, origin: Origin, options: LoadOptions
) -> list[Spectrum]:
    result = read_turbomole_vibspectrum(path)
    labels = tuple(str(i) for i in result.mode_index)
    imaginary = [
        lab for lab, flag in zip(labels, result.imaginary, strict=True) if flag
    ]
    inactive = [
        lab for lab, flag in zip(labels, result.ir_active, strict=True) if not flag
    ]
    extra = {}
    if imaginary:
        extra["imaginary_modes"] = ", ".join(imaginary)
    if inactive:
        extra["not_ir_active_modes"] = ", ".join(inactive)
    return [
        _sticks(
            path,
            technique,
            program="Turbomole",
            format_id="turbomole-vibspectrum",
            version=None,
            warnings=result.warnings,
            x=result.wavenumber_cm1,
            y=result.intensity_km_mol,
            ultraviolet=False,
            labels=labels,
            extra=extra,
        )
    ]


_REGISTRY: dict[str, FileFormat] = {
    f.id: f
    for f in (
        FileFormat(
            "table-text",
            "Text table (txt, csv, tsv, dat)",
            (".txt", ".csv", ".tsv", ".dat", ".asc"),
            False,
            _load_text,
        ),
        FileFormat(
            "table-sheet", "Spreadsheet (xlsx, ods)", SHEET_SUFFIXES, False, _load_sheet
        ),
        FileFormat("orca", "ORCA output (UV-Vis or IR block)", (), True, _load_orca),
        FileFormat(
            "turbomole-exspectrum",
            "Turbomole exspectrum",
            (),
            True,
            _turbomole_absorption(read_turbomole_exspectrum, "turbomole-exspectrum"),
        ),
        FileFormat(
            "turbomole-escf",
            "Turbomole escf.out",
            (),
            True,
            _turbomole_absorption(read_turbomole_escf, "turbomole-escf"),
        ),
        FileFormat(
            "turbomole-vibspectrum",
            "Turbomole vibspectrum",
            (),
            True,
            _load_turbomole_ir,
        ),
    )
}
