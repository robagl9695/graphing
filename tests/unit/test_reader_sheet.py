# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the spreadsheet readers (T2.2). Fixtures are generated here, by script."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import numpy as np
import pytest

from graphing.core.errors import (
    InvalidData,
    MalformedCell,
    NoNumericBlock,
    UnreadableFile,
)
from graphing.core.readers.sheet import read_sheet, sheet_names
from graphing.core.readers.text import read_text

WAVELENGTH = [300.0, 300.5, 301.0, 301.5, 302.0]
ABSORBANCE = [0.012, 0.0345, 1.5, 0.25, 0.0]
EXPECTED = np.column_stack([WAVELENGTH, ABSORBANCE])
HEADER = ["Wavelength(nm)", "Absorbance"]


def write_xlsx(
    path: Path, rows: list[list[object]], merges: tuple[str, ...] = ()
) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    for row in rows:
        sheet.append(row)
    for merge in merges:
        sheet.merge_cells(merge)
    workbook.save(path)


def write_ods(
    path: Path, sheets: dict[str, list[list[object]]], formulas: bool = False
) -> None:
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table, TableCell, TableRow
    from odf.text import P

    document = OpenDocumentSpreadsheet()
    for name, rows in sheets.items():
        table = Table(name=name)
        for values in rows:
            row = TableRow()
            for value in values:
                if isinstance(value, float):
                    attrs = {"valuetype": "float", "value": value}
                    if formulas:
                        attrs["formula"] = "of:=[.A1]*2"
                    cell = TableCell(**attrs)
                elif isinstance(value, str):
                    cell = TableCell(valuetype="string")
                    cell.addElement(P(text=value))
                else:
                    cell = TableCell()
                row.addElement(cell)
            table.addElement(row)
        document.spreadsheet.addElement(table)
    document.save(str(path))


def data_rows() -> list[list[object]]:
    return [list(pair) for pair in zip(WAVELENGTH, ABSORBANCE, strict=True)]


def test_csv_xlsx_and_ods_give_the_same_table(tmp_path: Path) -> None:
    rows = [HEADER, *data_rows()]
    csv = tmp_path / "s.csv"
    csv.write_text(
        "\n".join(
            ",".join(repr(c) if isinstance(c, float) else str(c) for c in r)
            for r in rows
        )
    )
    write_xlsx(tmp_path / "s.xlsx", rows)
    write_ods(tmp_path / "s.ods", {"Sheet1": rows})
    reference = read_text(csv)
    for name in ("s.xlsx", "s.ods"):
        table = read_sheet(tmp_path / name)
        np.testing.assert_array_equal(table.data, reference.data)
        assert table.columns == reference.columns


@pytest.mark.parametrize("suffix", [".xlsx", ".ods"])
def test_empty_leading_rows_and_columns_are_skipped(
    suffix: str, tmp_path: Path
) -> None:
    rows: list[list[object]] = [
        [],
        [None, "Instrument: synthetic"],
        [],
        [None, *HEADER],
        *[[None, *row] for row in data_rows()],
    ]
    path = tmp_path / f"lead{suffix}"
    if suffix == ".xlsx":
        write_xlsx(path, rows)
    else:
        write_ods(path, {"Sheet1": rows})
    table = read_sheet(path)
    np.testing.assert_array_equal(table.data, EXPECTED)
    assert table.columns == tuple(HEADER)
    assert table.preamble == ("Instrument: synthetic",)


def test_xlsx_merged_header_cells_are_filled(tmp_path: Path) -> None:
    rows: list[list[object]] = [["Sample A", None], *data_rows()]
    path = tmp_path / "merged.xlsx"
    write_xlsx(path, rows, merges=("A1:B1",))
    table = read_sheet(path)
    assert table.columns == ("Sample A", "Sample A")
    np.testing.assert_array_equal(table.data, EXPECTED)


def test_ods_merged_header_cells_are_filled(tmp_path: Path) -> None:
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import CoveredTableCell, Table, TableCell, TableRow
    from odf.text import P

    document = OpenDocumentSpreadsheet()
    table = Table(name="Sheet1")
    head = TableRow()
    merged = TableCell(valuetype="string", numbercolumnsspanned=2)
    merged.addElement(P(text="Sample A"))
    head.addElement(merged)
    head.addElement(CoveredTableCell())
    table.addElement(head)
    for x, y in zip(WAVELENGTH, ABSORBANCE, strict=True):
        row = TableRow()
        row.addElement(TableCell(valuetype="float", value=x))
        row.addElement(TableCell(valuetype="float", value=y))
        table.addElement(row)
    document.spreadsheet.addElement(table)
    path = tmp_path / "merged.ods"
    document.save(str(path))
    result = read_sheet(path)
    assert result.columns == ("Sample A", "Sample A")
    np.testing.assert_array_equal(result.data, EXPECTED)


def test_xlsx_formulas_are_read_by_stored_value(tmp_path: Path) -> None:
    path = tmp_path / "formula.xlsx"
    rows: list[list[object]] = [HEADER, [1.0, "=A2*2"], [2.0, "=A3*2"], [3.0, "=A4*2"]]
    write_xlsx(path, rows)
    # openpyxl cannot calculate: store the values a spreadsheet would have cached.
    patched = tmp_path / "patched.xlsx"
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(patched, "w") as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                xml = content.decode()
                for ref, number in (("B2", 2), ("B3", 4), ("B4", 6)):
                    xml, count = re.subn(
                        rf'(<c r="{ref}"[^>]*><f>[^<]*</f>)(<v\s*/>|<v></v>)',
                        rf"\g<1><v>{number}</v>",
                        xml,
                    )
                    assert count == 1
                content = xml.encode()
            target.writestr(item, content)
    table = read_sheet(patched)
    np.testing.assert_array_equal(table.data, [[1.0, 2.0], [2.0, 4.0], [3.0, 6.0]])


def test_ods_formulas_are_read_by_stored_value(tmp_path: Path) -> None:
    path = tmp_path / "formula.ods"
    write_ods(path, {"Sheet1": [[1.0, 2.0], [2.0, 4.0]]}, formulas=True)
    np.testing.assert_array_equal(read_sheet(path).data, [[1.0, 2.0], [2.0, 4.0]])


def test_sheet_selection_by_name_and_index(tmp_path: Path) -> None:
    path = tmp_path / "two.ods"
    write_ods(
        path,
        {
            "Notes": [["no numbers here"]],
            "Data": [HEADER, *data_rows()],
            "Other": [[1.0, 2.0]],
        },
    )
    assert sheet_names(path) == ["Notes", "Data", "Other"]
    np.testing.assert_array_equal(read_sheet(path).data, EXPECTED)  # first with numbers
    np.testing.assert_array_equal(read_sheet(path, "Data").data, EXPECTED)
    np.testing.assert_array_equal(read_sheet(path, 2).data, [[1.0, 2.0]])
    with pytest.raises(InvalidData, match="no sheet named 'Nope'"):
        read_sheet(path, "Nope")
    with pytest.raises(InvalidData, match="no sheet 7"):
        read_sheet(path, 7)
    with pytest.raises(NoNumericBlock):
        read_sheet(path, "Notes")


def test_workbook_without_numbers_raises(tmp_path: Path) -> None:
    path = tmp_path / "words.xlsx"
    write_xlsx(path, [["a", "b"], ["c", "d"]])
    with pytest.raises(NoNumericBlock):
        read_sheet(path)


def test_ods_with_huge_empty_row_repeat_is_cheap(tmp_path: Path) -> None:
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table, TableCell, TableRow

    document = OpenDocumentSpreadsheet()
    table = Table(name="Sheet1")
    for x, y in ((1.0, 2.0), (3.0, 4.0)):
        row = TableRow()
        row.addElement(TableCell(valuetype="float", value=x))
        row.addElement(TableCell(valuetype="float", value=y))
        row.addElement(TableCell(numbercolumnsrepeated=16000))
        table.addElement(row)
    table.addElement(TableRow(numberrowsrepeated=1048000))
    document.spreadsheet.addElement(table)
    path = tmp_path / "padded.ods"
    document.save(str(path))
    np.testing.assert_array_equal(read_sheet(path).data, [[1.0, 2.0], [3.0, 4.0]])


def test_missing_corrupt_and_unsupported_files(tmp_path: Path) -> None:
    with pytest.raises(UnreadableFile, match="does not exist"):
        read_sheet(tmp_path / "missing.xlsx")
    bad = tmp_path / "bad.xlsx"
    bad.write_bytes(b"this is not a zip file")
    with pytest.raises(UnreadableFile, match="bad.xlsx"):
        read_sheet(bad)
    other = tmp_path / "old.xls"
    other.write_bytes(b"")
    with pytest.raises(UnreadableFile, match="not an xlsx or ods"):
        read_sheet(other)


def test_skip_rows_and_header_overrides(tmp_path: Path) -> None:
    path = tmp_path / "o.xlsx"
    write_xlsx(path, [["title"], HEADER, *data_rows()])
    table = read_sheet(path)
    assert table.settings.skip_rows == 2
    assert table.settings.has_header is True
    from graphing.core.readers.text import ReadSettings

    assert read_sheet(path, settings=ReadSettings(has_header=False)).columns is None
    np.testing.assert_array_equal(
        read_sheet(path, settings=ReadSettings(skip_rows=2)).data, EXPECTED
    )
    with pytest.raises(NoNumericBlock):
        read_sheet(path, settings=ReadSettings(skip_rows=0))


@pytest.mark.parametrize("suffix", [".xlsx", ".ods"])
@pytest.mark.parametrize(
    ("bad_row", "message"),
    [
        (3, "Row 5, column 2"),  # empty cell in the middle of the column
        (None, "Row 5, column 2"),  # same, written as text "N/A" below
    ],
)
def test_empty_or_text_cell_inside_the_table_is_an_error(
    suffix: str, bad_row: int | None, message: str, tmp_path: Path
) -> None:
    rows = [HEADER, *data_rows()]
    rows[4] = [rows[4][0], None if bad_row is not None else "N/A"]
    path = tmp_path / f"broken{suffix}"
    if suffix == ".xlsx":
        write_xlsx(path, rows)
    else:
        write_ods(path, {"Sheet1": rows})
    with pytest.raises(MalformedCell, match=message):
        read_sheet(path)


def test_missing_last_value_in_a_sheet_is_an_error(tmp_path: Path) -> None:
    rows = [HEADER, *data_rows()]
    rows[-1] = [rows[-1][0], None]
    path = tmp_path / "last.xlsx"
    write_xlsx(path, rows)
    with pytest.raises(MalformedCell, match="Row 6, column 2"):
        read_sheet(path)


def test_text_around_a_clean_sheet_table_is_not_an_error(tmp_path: Path) -> None:
    rows: list[list[object]] = [
        ["Date", 2026.0],
        ["Note"],
        HEADER,
        *data_rows(),
        ["Total", "five"],
    ]
    path = tmp_path / "clean.xlsx"
    write_xlsx(path, rows)
    np.testing.assert_array_equal(read_sheet(path).data, EXPECTED)
