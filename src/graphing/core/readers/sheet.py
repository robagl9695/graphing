# SPDX-License-Identifier: GPL-3.0-or-later
"""Reader of spreadsheet files (xlsx, ods) into the same :class:`Table` as text files.

Both formats are first turned into a grid of cells (``float``, ``str`` or ``None``);
the numeric block, the header and the preamble are then found on that grid. Formulas
are read by the value stored in the file, never recalculated.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from graphing.core.errors import (
    InvalidData,
    MalformedCell,
    NoNumericBlock,
    UnreadableFile,
)
from graphing.core.readers.text import ReadSettings, Table

Cell = float | str | None
Grid = list[list[Cell]]

#: Repeated empty cells beyond this count are padding at the end of a row, not a gap.
_MAX_EMPTY_REPEAT = 1024
#: Repeated non-empty rows beyond this count are treated as a damaged file.
_MAX_ROW_REPEAT = 100_000

SUPPORTED_SUFFIXES: tuple[str, ...] = (".xlsx", ".ods")


@dataclass(frozen=True)
class _Block:
    start: int  # first numeric row
    end: int  # exclusive
    first_col: int
    last_col: int  # inclusive


def sheet_names(path: str | Path) -> list[str]:
    """Return the names of the sheets of a spreadsheet file, in order."""
    return [name for name, _ in _load_sheets(Path(path))]


def read_sheet(
    path: str | Path,
    sheet: str | int | None = None,
    settings: ReadSettings | None = None,
) -> Table:
    """Read the numeric block of a sheet of an xlsx or ods file.

    Parameters
    ----------
    path
        File to read.
    sheet
        Sheet name or position (from 0). ``None`` takes the first sheet that has a
        numeric block.
    settings
        Only ``skip_rows`` (index of the first numeric row) and ``has_header`` apply;
        encoding, delimiter and decimal separator mean nothing for a spreadsheet.

    Returns
    -------
    Table
        The numeric block; ``settings`` holds the ``skip_rows`` and ``has_header``
        used.

    Raises
    ------
    UnreadableFile
        The file is missing, corrupt or of an unsupported type.
    InvalidData
        The sheet asked for does not exist.
    NoNumericBlock
        The sheet has no block of numeric rows with at least two columns.
    """
    path = Path(path)
    settings = settings or ReadSettings()
    sheets = _load_sheets(path)
    if sheet is None:
        for name, grid in sheets:
            try:
                return _table(grid, settings, f"{path} [{name}]")
            except NoNumericBlock:
                continue
        raise NoNumericBlock(f"No sheet of '{path}' has a block of numeric rows.")
    return _table(_pick(sheets, sheet, path), settings, f"{path} [{sheet}]")


def _pick(sheets: list[tuple[str, Grid]], sheet: str | int, path: Path) -> Grid:
    if isinstance(sheet, int):
        if 0 <= sheet < len(sheets):
            return sheets[sheet][1]
        raise InvalidData(
            f"'{path}' has {len(sheets)} sheets; there is no sheet {sheet}."
        )
    for name, grid in sheets:
        if name == sheet:
            return grid
    names = ", ".join(name for name, _ in sheets)
    raise InvalidData(f"'{path}' has no sheet named '{sheet}' (sheets: {names}).")


def _load_sheets(path: Path) -> list[tuple[str, Grid]]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise UnreadableFile(
            f"'{path}' is not an xlsx or ods file (found '{path.suffix}')."
        )
    if not path.is_file():
        raise UnreadableFile(f"Cannot read '{path}': the file does not exist.")
    try:
        return _load_xlsx(path) if suffix == ".xlsx" else _load_ods(path)
    except UnreadableFile:
        raise
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as error:
        raise UnreadableFile(
            f"Cannot read '{path}': the file is damaged ({error})."
        ) from error


def _load_xlsx(path: Path) -> list[tuple[str, Grid]]:
    from openpyxl import load_workbook  # type: ignore[import-untyped]

    workbook = load_workbook(path, data_only=True)  # formulas by stored value
    sheets: list[tuple[str, Grid]] = []
    for worksheet in workbook.worksheets:
        grid: Grid = [
            [_clean(value) for value in row]
            for row in worksheet.iter_rows(min_row=1, min_col=1, values_only=True)
        ]
        for merged in worksheet.merged_cells.ranges:
            # Only the top-left cell of a merged range holds the value.
            top_left = grid[merged.min_row - 1][merged.min_col - 1]
            for r in range(merged.min_row - 1, merged.max_row):
                for c in range(merged.min_col - 1, merged.max_col):
                    grid[r][c] = top_left
        sheets.append((worksheet.title, grid))
    return sheets


def _clean(value: Any) -> Cell:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int | float):
        return float(value)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_ods(path: Path) -> list[tuple[str, Grid]]:
    from odf.opendocument import load  # type: ignore[import-untyped]
    from odf.table import Table as OdfTable  # type: ignore[import-untyped]
    from odf.table import TableRow

    document = load(str(path))
    sheets: list[tuple[str, Grid]] = []
    for table in document.spreadsheet.getElementsByType(OdfTable):
        grid: Grid = []
        for row in table.getElementsByType(TableRow):
            cells: list[Cell] = []
            spanned: tuple[Cell, int] = (
                None,
                0,
            )  # value and covered cells still to fill
            for cell in row.childNodes:
                if cell.qname[1] == "covered-table-cell":
                    if spanned[1] > 0:
                        cells.append(spanned[0])
                        spanned = (spanned[0], spanned[1] - 1)
                        continue
                    cells.append(None)
                    continue
                if cell.qname[1] != "table-cell":
                    continue
                value = _ods_value(cell)
                repeat = int(cell.getAttribute("numbercolumnsrepeated") or 1)
                span = int(cell.getAttribute("numbercolumnsspanned") or 1)
                if value is None and repeat > _MAX_EMPTY_REPEAT:
                    continue  # trailing padding
                cells.extend([value] * repeat)
                spanned = (value, span - 1)
            row_repeat = int(row.getAttribute("numberrowsrepeated") or 1)
            if all(cell is None for cell in cells):
                grid.extend([[] for _ in range(min(row_repeat, 1))])
                continue
            if row_repeat > _MAX_ROW_REPEAT:
                raise UnreadableFile(
                    f"Sheet '{table.getAttribute('name')}' repeats a row too often."
                )
            grid.extend([list(cells) for _ in range(row_repeat)])
        sheets.append((str(table.getAttribute("name")), grid))
    return sheets


def _ods_value(cell: Any) -> Cell:
    from odf import teletype  # type: ignore[import-untyped]

    kind = cell.getAttribute("valuetype")
    if kind in ("float", "percentage", "currency"):
        return float(cell.getAttribute("value"))
    text = teletype.extractText(cell).strip()
    return text or None


def _span(row: list[Cell]) -> tuple[int, int] | None:
    """Return ``(first, last)`` used column of a row, or ``None`` if it is blank."""
    used = [i for i, cell in enumerate(row) if cell is not None]
    return (used[0], used[-1]) if used else None


def _is_numeric_row(row: list[Cell], span: tuple[int, int] | None) -> bool:
    if span is None or span[1] - span[0] < 1:
        return False
    return all(
        isinstance(cell, float) and np.isfinite(cell)
        for cell in row[span[0] : span[1] + 1]
    )


def _find_block(grid: Grid, skip_rows: int | None) -> _Block | None:
    """Longest run of numeric rows sharing the same columns; blank rows are ignored.

    With ``skip_rows`` the block must begin at the first non-blank row from there.
    """
    best: _Block | None = None
    best_rows = 0
    run: _Block | None = None
    rows = 0
    for index in range(skip_rows or 0, len(grid)):
        span = _span(grid[index])
        if span is None:
            continue
        if not _is_numeric_row(grid[index], span):
            if skip_rows is not None:
                break
            run, rows = None, 0
            continue
        if run is not None and (run.first_col, run.last_col) == span:
            run, rows = _Block(run.start, index + 1, *span), rows + 1
        elif skip_rows is not None and run is not None:
            break
        else:
            run, rows = _Block(index, index + 1, *span), 1
        if rows > best_rows:
            best, best_rows = run, rows
    return best


def _interrupts(grid: Grid, index: int, step: int, block: _Block) -> int | None:
    """Column (from 0) of the cell that breaks a data row next to the block, if any.

    Same rule as the text reader: a row with no number never interrupts; a row with
    numbers does when its first cell in the block's columns is a number but another
    cell there is empty or text, or when more numeric rows lie beyond it.
    """
    columns = range(block.first_col, block.last_col + 1)
    cells = [grid[index][c] if c < len(grid[index]) else None for c in columns]
    if not any(isinstance(cell, float) for cell in cells):
        return None
    bad = next(
        (
            c
            for c, cell in zip(columns, cells, strict=True)
            if not isinstance(cell, float)
        ),
        None,
    )
    if bad is None:
        return None
    beyond = range(index + step, len(grid) if step > 0 else -1, step)
    far_data = any(
        _span(grid[i]) == (block.first_col, block.last_col)
        and _is_numeric_row(grid[i], _span(grid[i]))
        for i in beyond
    )
    return bad if isinstance(cells[0], float) or far_data else None


def _check_interruptions(
    grid: Grid, block: _Block, skip_rows: int | None, source: str
) -> None:
    """Raise when a broken data row sits right next to the chosen block."""
    neighbours = [
        (next((i for i in range(block.end, len(grid)) if _span(grid[i])), None), 1)
    ]
    if skip_rows is None:
        neighbours.append(
            (
                next(
                    (i for i in range(block.start - 1, -1, -1) if _span(grid[i])), None
                ),
                -1,
            )
        )
    for index, step in neighbours:
        if index is None:
            continue
        column = _interrupts(grid, index, step, block)
        if column is not None:
            raise MalformedCell(
                f"Row {index + 1}, column {column + 1} of {source} is empty or not a "
                f"number, which breaks the table of numbers (rows {block.start + 1} to "
                f"{block.end}). Fix or fill that cell; otherwise part of the data "
                "would be dropped."
            )


def _table(grid: Grid, settings: ReadSettings, source: str) -> Table:
    if settings.skip_rows is not None and settings.skip_rows < 0:
        raise InvalidData("skip_rows cannot be negative.")
    block = _find_block(grid, settings.skip_rows)
    if block is None:
        raise NoNumericBlock(
            f"No block of numeric rows with at least two columns was found in {source}."
        )
    _check_interruptions(grid, block, settings.skip_rows, source)
    columns_range = slice(block.first_col, block.last_col + 1)
    rows = [
        grid[i][columns_range]
        for i in range(block.start, block.end)
        if _span(grid[i]) is not None
    ]
    data = np.array(rows, dtype=np.float64)

    header_index = _header_index(grid, block, settings.has_header)
    columns = (
        tuple(
            str(cell) if cell is not None else ""
            for cell in _padded(grid[header_index], block.last_col + 1)[columns_range]
        )
        if header_index is not None
        else None
    )
    preamble_end = block.start if header_index is None else header_index
    preamble = tuple(
        " ".join(str(cell) for cell in row if cell is not None)
        for row in grid[:preamble_end]
        if _span(row) is not None
    )
    return Table(
        data=data,
        columns=columns,
        settings=ReadSettings(skip_rows=block.start, has_header=columns is not None),
        preamble=preamble,
    )


def _padded(row: list[Cell], length: int) -> list[Cell]:
    return row + [None] * (length - len(row))


def _header_index(grid: Grid, block: _Block, has_header: bool | None) -> int | None:
    """The nearest non-blank row above the block, when it holds only text."""
    if has_header is False:
        return None
    for index in range(block.start - 1, -1, -1):
        span = _span(grid[index])
        if span is None:
            continue
        cells = _padded(grid[index], block.last_col + 1)[
            block.first_col : block.last_col + 1
        ]
        if any(cell is not None for cell in cells) and all(
            cell is None or isinstance(cell, str) for cell in cells
        ):
            return index
        break
    if has_header:
        raise NoNumericBlock(
            "A header row was requested but none precedes the numeric block."
        )
    return None
