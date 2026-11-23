# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the delimited text reader (T2.1). Fixtures are synthetic spectra."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from graphing.core.errors import (
    AmbiguousFormat,
    InvalidData,
    MalformedCell,
    NoNumericBlock,
    UnreadableFile,
)
from graphing.core.readers.text import ReadSettings, Table, parse_text, read_text

WAVELENGTH = np.array([300.0, 300.5, 301.0, 301.5, 302.0])
ABSORBANCE = np.array([0.012, 0.0345, 1.5, 0.25, 0.0])
EXPECTED = np.column_stack([WAVELENGTH, ABSORBANCE])

DELIMITERS = {"tab": "\t", "semicolon": ";", "comma": ",", "space": " "}
DECIMALS = {"point": ".", "comma": ","}
PREAMBLE = [
    "Instrument: synthetic spectrophotometer",
    "Date: 2026-11-16",
    "",
    "Sample 1",
]


def make_text(delimiter: str, decimal: str, preamble: bool, header: bool = True) -> str:
    lines = list(PREAMBLE) if preamble else []
    if header:
        lines.append(f"Wavelength(nm){delimiter}Absorbance")
    for x, y in zip(WAVELENGTH, ABSORBANCE, strict=True):
        cells = [
            repr(float(x)).replace(".", decimal),
            repr(float(y)).replace(".", decimal),
        ]
        lines.append(delimiter.join(cells))
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("preamble", [False, True], ids=["bare", "preamble"])
@pytest.mark.parametrize("decimal", DECIMALS.values(), ids=DECIMALS.keys())
@pytest.mark.parametrize("delimiter", DELIMITERS.values(), ids=DELIMITERS.keys())
def test_sixteen_combinations_give_identical_tables(
    delimiter: str, decimal: str, preamble: bool, tmp_path: Path
) -> None:
    if delimiter == decimal:
        pytest.skip("not a valid combination")  # pragma: no cover
    path = tmp_path / "spectrum.txt"
    path.write_text(make_text(delimiter, decimal, preamble), encoding="utf-8")
    table = read_text(path)
    np.testing.assert_array_equal(table.data, EXPECTED)
    assert table.settings.delimiter == delimiter
    assert table.settings.decimal == decimal
    assert table.columns == ("Wavelength(nm)", "Absorbance")


def test_comma_delimiter_with_comma_decimal_is_reported_not_guessed() -> None:
    # Two columns written "1,5,2,5" per row: delimiter and decimal are both commas.
    text = "1,5,2,5\n2,5,3,5\n3,5,4,5\n"
    with pytest.raises(AmbiguousFormat, match="decimal"):
        parse_text(text)


def test_ambiguity_is_resolved_by_explicit_settings() -> None:
    text = "1,5,2,5\n2,5,3,5\n"
    as_integers = parse_text(text, ReadSettings(delimiter=",", decimal="."))
    assert as_integers.data.shape == (2, 4)
    as_decimals = parse_text(
        text.replace("5,2", "5;2").replace("5,3", "5;3"),
        ReadSettings(delimiter=";", decimal=","),
    )
    np.testing.assert_array_equal(as_decimals.data[0], [1.5, 2.5])


@pytest.mark.parametrize(
    "text", ["", "\n\n", "only words\nand more words\n", "1\n2\n3\n"]
)
def test_no_numeric_block_raises_named_error(text: str) -> None:
    with pytest.raises(NoNumericBlock):
        parse_text(text, source="empty.txt")


def test_missing_file_raises_named_error(tmp_path: Path) -> None:
    with pytest.raises(UnreadableFile, match="missing.txt"):
        read_text(tmp_path / "missing.txt")


def test_header_is_optional(tmp_path: Path) -> None:
    path = tmp_path / "no_header.csv"
    path.write_text(make_text(",", ".", False, header=False), encoding="utf-8")
    table = read_text(path)
    assert table.columns is None
    np.testing.assert_array_equal(table.data, EXPECTED)


def test_preamble_is_returned_and_skip_rows_reported() -> None:
    table = parse_text(make_text("\t", ".", True))
    assert table.preamble[0].startswith("Instrument")
    assert table.settings.skip_rows == 5  # 4 preamble lines + 1 header line
    assert table.settings.has_header is True


def test_trailing_text_after_the_block_is_ignored() -> None:
    text = make_text(";", ",", False) + "\nEnd of file\n"
    np.testing.assert_array_equal(parse_text(text).data, EXPECTED)


def test_longest_numeric_block_wins_over_stray_numeric_line() -> None:
    text = "1 2\nsome title\n" + make_text(" ", ".", False)
    np.testing.assert_array_equal(parse_text(text).data, EXPECTED)


def test_extra_columns_and_trailing_delimiter() -> None:
    text = "400;0,1;0,2;\n401;0,3;0,4;\n"
    table = parse_text(text)
    assert table.data.shape == (2, 3)
    assert table.settings.decimal == ","


def test_scientific_and_fortran_exponents() -> None:
    table = parse_text("1.0E+02 2.5e-3\n2.0D+02 -3.5D-01\n")
    np.testing.assert_allclose(table.data, [[100.0, 2.5e-3], [200.0, -0.35]])


def test_blank_lines_inside_the_block_are_ignored() -> None:
    table = parse_text("1,2\n\n3,4\n5,6\n".replace(",", "\t"))
    assert table.data.shape == (3, 2)


@pytest.mark.parametrize(
    ("encoding", "bom"),
    [("utf-8", b""), ("utf-8", b"\xef\xbb\xbf"), ("cp1252", b""), ("utf-16", b"")],
)
def test_encodings_are_detected(encoding: str, bom: bytes, tmp_path: Path) -> None:
    text = "Longitud de onda (nm);Absorbancia (ángulo)\n" + make_text(
        ";", ",", False, False
    )
    path = tmp_path / "enc.csv"
    path.write_bytes(bom + text.encode(encoding))
    table = read_text(path)
    np.testing.assert_array_equal(table.data, EXPECTED)
    assert table.columns is not None
    assert "ángulo" in table.columns[1]


def test_undecodable_with_forced_encoding_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.txt"
    path.write_bytes("1;2\n".encode("utf-16"))
    with pytest.raises(UnreadableFile):
        read_text(path, ReadSettings(encoding="ascii"))


def test_overrides_are_respected_and_reported() -> None:
    text = make_text("\t", ".", True)
    table = parse_text(
        text, ReadSettings(delimiter="\t", decimal=".", skip_rows=5, has_header=True)
    )
    np.testing.assert_array_equal(table.data, EXPECTED)
    assert table.columns == ("Wavelength(nm)", "Absorbance")


def test_skip_rows_override_must_point_at_numbers() -> None:
    with pytest.raises(NoNumericBlock):
        parse_text(make_text("\t", ".", True), ReadSettings(skip_rows=0))


def test_header_forced_on_but_absent_raises() -> None:
    with pytest.raises(NoNumericBlock, match="header"):
        parse_text("1 2\n3 4\n", ReadSettings(has_header=True))


def test_header_forced_off_keeps_names_out() -> None:
    table = parse_text(make_text(",", ".", False), ReadSettings(has_header=False))
    assert table.columns is None


@pytest.mark.parametrize(
    "settings",
    [
        ReadSettings(delimiter="|"),
        ReadSettings(decimal=";"),
        ReadSettings(delimiter=",", decimal=","),
        ReadSettings(skip_rows=-1),
    ],
)
def test_invalid_settings_raise(settings: ReadSettings) -> None:
    with pytest.raises(InvalidData):
        parse_text("1 2\n", settings)


def test_table_is_a_float_array() -> None:
    table: Table = parse_text("1 2\n3 4\n")
    assert table.data.dtype == np.float64


def hundred_rows(bad_index: int, bad_row: str, delimiter: str = " ") -> str:
    rows = [f"{300 + i}{delimiter}{i / 10}" for i in range(100)]
    rows[bad_index] = bad_row
    return "\n".join(rows) + "\n"


@pytest.mark.parametrize(
    ("bad_index", "bad_row", "line"),
    [
        (49, "349 5.0x", 50),  # typo in the middle: used to keep only 50 rows
        (10, "310;OVRFLW", 11),  # overflow marker of a detector
        (89, "389;N/A", 90),
        (99, "399;", 100),  # last row cut short: first cell is a number
    ],
)
def test_bad_cell_in_the_table_is_an_error_not_a_truncation(
    bad_index: int, bad_row: str, line: int
) -> None:
    delimiter = ";" if ";" in bad_row else " "
    text = hundred_rows(bad_index, bad_row, delimiter)
    if delimiter == ";":
        text = text.replace("\n3", "\n3")  # rows keep the chosen delimiter
    with pytest.raises(MalformedCell, match=f"Line {line} of data.txt"):
        parse_text(text, source="data.txt")


def test_missing_value_at_the_end_of_a_row_is_reported() -> None:
    text = "300;0,1\n310;\n320;0,3\n330;0,4\n"
    with pytest.raises(MalformedCell, match="Line 2"):
        parse_text(text)


def test_empty_cell_in_a_middle_column_is_reported() -> None:
    text = "300;0,1;0,5\n310;;0,6\n320;0,3;0,7\n330;0,4;0,8\n"
    with pytest.raises(MalformedCell, match="Line 2"):
        parse_text(text)


def test_row_with_a_bad_first_cell_is_reported_when_data_lie_beyond() -> None:
    text = "300 0.1\n310 0.2\nN/A 0.3\n330 0.4\n340 0.5\n"
    with pytest.raises(MalformedCell, match="Line 3"):
        parse_text(text)


def test_message_names_what_to_do() -> None:
    with pytest.raises(MalformedCell, match="Fix or delete that line"):
        parse_text("1 2\n3 x\n5 6\n7 8\n")


def test_text_next_to_the_block_still_never_interrupts() -> None:
    # Title, numeric range line, header and footer around a clean table.
    text = (
        "Sample 1\n4000 400\nWavelength Abs\n"
        "300 0.1\n310 0.2\n320 0.3\nEnd of file 2026\n"
    )
    assert parse_text(text).data.shape == (3, 2)
    # A title with a number right above headerless data is not a data row either.
    assert parse_text("Sample 1\n300 0.1\n310 0.2\n").data.shape == (2, 2)


def test_skip_rows_override_bypasses_the_check_before_the_table() -> None:
    text = "300 oops\n310 0.2\n320 0.3\n"
    with pytest.raises(MalformedCell):
        parse_text(text)
    table = parse_text(text, ReadSettings(skip_rows=1))
    np.testing.assert_array_equal(table.data, [[310.0, 0.2], [320.0, 0.3]])
