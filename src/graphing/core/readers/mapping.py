# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn a read :class:`Table` into spectra, following the user's column choices.

The user always declares the technique, the origin, the quantities and the units.
:func:`suggest_mapping` only proposes; nothing is built from a suggestion until the
caller completes it with :meth:`MappingSuggestion.to_mapping`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from graphing.core.data import CurveData
from graphing.core.errors import InvalidMapping, NonNumericCells
from graphing.core.readers.text import Table
from graphing.core.spectrum import Origin, Spectrum, Technique
from graphing.core.units import DEFAULT_UNIT, X_QUANTITIES, Quantity, Unit

_MAX_ROWS_LISTED = 5


@dataclass(frozen=True, kw_only=True)
class ColumnMapping:
    """Complete, confirmed choices for turning columns into spectra.

    Attributes
    ----------
    x_column
        Index (from 0) of the x column.
    y_columns
        Indices of the y columns; each one becomes a spectrum.
    x_quantity, x_unit
        What the x column measures and in which unit.
    y_quantity
        What the y columns measure; the unit is the quantity's own.
    technique, origin
        Declared by the user, never inferred.
    """

    x_column: int
    y_columns: tuple[int, ...]
    x_quantity: Quantity
    x_unit: Unit
    y_quantity: Quantity
    technique: Technique
    origin: Origin


@dataclass(frozen=True, kw_only=True)
class MappingSuggestion:
    """A proposal read from the table; fields that cannot be guessed are ``None``."""

    x_column: int
    y_columns: tuple[int, ...]
    x_quantity: Quantity | None
    x_unit: Unit | None
    y_quantity: Quantity | None

    def to_mapping(
        self,
        technique: Technique,
        origin: Origin,
        x_quantity: Quantity | None = None,
        x_unit: Unit | None = None,
        y_quantity: Quantity | None = None,
    ) -> ColumnMapping:
        """Confirm the suggestion; the caller always supplies technique and origin.

        Raises
        ------
        InvalidMapping
            A quantity is neither suggested nor supplied.
        """
        quantity_x = x_quantity or self.x_quantity
        quantity_y = y_quantity or self.y_quantity
        if quantity_x is None or quantity_y is None:
            raise InvalidMapping(
                "The x and y quantities could not be guessed from the column names; "
                "choose them."
            )
        unit_x = x_unit or (self.x_unit if x_quantity is None else None)
        return ColumnMapping(
            x_column=self.x_column,
            y_columns=self.y_columns,
            x_quantity=quantity_x,
            x_unit=unit_x or DEFAULT_UNIT[quantity_x],
            y_quantity=quantity_y,
            technique=technique,
            origin=origin,
        )


_X_HINTS: tuple[tuple[re.Pattern[str], Quantity], ...] = (
    (
        re.compile(r"cm\s*(\^?-1|⁻¹)|wavenumber|número de onda|numero de onda"),
        Quantity.WAVENUMBER,
    ),
    (re.compile(r"\bnm\b|wavelength|longitud de onda|λ"), Quantity.WAVELENGTH),
    (re.compile(r"\bev\b|energy|energía|energia"), Quantity.ENERGY),
)
_Y_HINTS: tuple[tuple[re.Pattern[str], Quantity], ...] = (
    (re.compile(r"%\s*t\b|transmit"), Quantity.TRANSMITTANCE),
    (re.compile(r"\babs|absorb"), Quantity.ABSORBANCE),
    (re.compile(r"ε|epsilon|molar|absortividad"), Quantity.MOLAR_ABSORPTIVITY),
    (re.compile(r"intens"), Quantity.INTENSITY),
)


def _hint(
    text: str, hints: tuple[tuple[re.Pattern[str], Quantity], ...]
) -> Quantity | None:
    lowered = text.lower()
    for pattern, quantity in hints:
        if pattern.search(lowered):
            return quantity
    return None


def suggest_mapping(table: Table) -> MappingSuggestion:
    """Propose a mapping: first column is x, every other column is a y.

    Quantities are read from the header text when it says so (``nm``, ``cm-1``,
    ``Abs``, ``%T``...). The technique and the origin are never suggested.
    """
    ncols = table.data.shape[1]
    x_quantity: Quantity | None = None
    y_quantity: Quantity | None = None
    if table.columns is not None:
        x_quantity = _hint(table.columns[0], _X_HINTS)
        found = {_hint(name, _Y_HINTS) for name in table.columns[1:]}
        y_quantity = found.pop() if len(found) == 1 else None
    return MappingSuggestion(
        x_column=0,
        y_columns=tuple(range(1, ncols)),
        x_quantity=x_quantity,
        x_unit=DEFAULT_UNIT[x_quantity] if x_quantity else None,
        y_quantity=y_quantity,
    )


def build_spectra(
    table: Table, mapping: ColumnMapping, source: str = ""
) -> list[Spectrum]:
    """Build one :class:`Spectrum` per y column, all sharing the x column.

    Rows are put in ascending x order when the file lists them otherwise (common in
    IR exports); this is recorded in the metadata ``"x_reordered"``.

    Parameters
    ----------
    table
        Result of a reader.
    mapping
        Confirmed column choices.
    source
        File name stored in the metadata and used in messages.

    Raises
    ------
    InvalidMapping
        A column index is out of range, a column is used twice, no y column was
        chosen, or the x values repeat.
    NonNumericCells
        A chosen column holds ``nan`` or infinite values; the rows are named.
    """
    ncols = table.data.shape[1]
    _check_columns(mapping, ncols)
    first_line = (table.settings.skip_rows or 0) + 1  # first row of the block, from 1
    where = f" in {source}" if source else ""

    for column in (mapping.x_column, *mapping.y_columns):
        bad = np.flatnonzero(~np.isfinite(table.data[:, column]))
        if bad.size:
            rows = ", ".join(str(int(i) + 1) for i in bad[:_MAX_ROWS_LISTED])
            more = ", ..." if bad.size > _MAX_ROWS_LISTED else ""
            raise NonNumericCells(
                f"Column {column + 1} ({_name(table, column)}){where} has values that "
                f"are not numbers at row(s) {rows}{more} of the numeric block, which "
                f"starts at line {first_line}."
            )

    x = table.data[:, mapping.x_column]
    order = np.argsort(x, kind="stable")
    reordered = not np.array_equal(order, np.arange(x.size))
    x_sorted = x[order]
    repeated = np.flatnonzero(np.diff(x_sorted) == 0)
    if repeated.size:
        value = x_sorted[repeated[0]]
        raise InvalidMapping(
            f"The x column ({_name(table, mapping.x_column)}){where} repeats the value "
            f"{value:g}; x must be strictly ascending, so choose another x column."
        )

    y_unit = DEFAULT_UNIT[mapping.y_quantity]
    spectra: list[Spectrum] = []
    for column in mapping.y_columns:
        metadata = {
            "column": str(column + 1),
            "x_reordered": "yes" if reordered else "no",
        }
        if source:
            metadata["source"] = source
        if table.preamble:
            metadata["preamble"] = "\n".join(table.preamble)
        spectra.append(
            Spectrum(
                name=_name(table, column),
                data=CurveData(
                    x=x_sorted,
                    y=table.data[order, column],
                    x_quantity=mapping.x_quantity,
                    x_unit=mapping.x_unit,
                    y_quantity=mapping.y_quantity,
                    y_unit=y_unit,
                ),
                metadata=metadata,
                technique=mapping.technique,
                origin=mapping.origin,
            )
        )
    return spectra


def _name(table: Table, column: int) -> str:
    if table.columns is not None and table.columns[column].strip():
        return table.columns[column].strip()
    return f"Column {column + 1}"


def _check_columns(mapping: ColumnMapping, ncols: int) -> None:
    if mapping.x_quantity not in X_QUANTITIES:
        raise InvalidMapping(f"{mapping.x_quantity.value} cannot be the x quantity.")
    if not mapping.y_columns:
        raise InvalidMapping("Choose at least one y column.")
    chosen = (mapping.x_column, *mapping.y_columns)
    for column in chosen:
        if not 0 <= column < ncols:
            raise InvalidMapping(
                f"Column {column + 1} does not exist; the table has {ncols} columns."
            )
    if len(set(chosen)) != len(chosen):
        raise InvalidMapping("A column cannot be used twice (as x and y, or as two y).")
