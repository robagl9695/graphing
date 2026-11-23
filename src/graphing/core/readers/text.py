# SPDX-License-Identifier: GPL-3.0-or-later
"""Reader of delimited text files (txt, csv) with automatic format detection.

The reader finds, for a file the user never described: the text encoding, the field
delimiter, the decimal separator, the preamble to skip and an optional header row.
Every detected setting can be overridden through :class:`ReadSettings`. When the
file cannot be interpreted with confidence the reader raises a named error instead
of guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from graphing.core.errors import (
    AmbiguousFormat,
    InvalidData,
    MalformedCell,
    NoNumericBlock,
    UnreadableFile,
)

#: Candidate delimiters in order of preference. A single space means "any run of
#: whitespace".
DELIMITERS: tuple[str, ...] = ("\t", ";", ",", " ")
DECIMALS: tuple[str, ...] = (".", ",")

#: Encodings tried in order after the byte-order marks. cp1252 covers the exports of
#: Windows instrument software; latin-1 never fails and is the last resort.
_FALLBACK_ENCODINGS: tuple[str, ...] = ("utf-8", "cp1252", "latin-1")

# Fortran-style exponents (1.0D+02) appear in some program outputs.
_NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eEdD][+-]?\d+)?$")
_INTEGER = re.compile(r"^\d+$")


@dataclass(frozen=True)
class ReadSettings:
    """Format settings of a delimited text file. ``None`` means "detect it".

    Attributes
    ----------
    encoding
        Python codec name, e.g. ``"utf-8"``.
    delimiter
        One of tab, ``";"``, ``","`` or a single space (any run of whitespace).
    decimal
        ``"."`` or ``","``.
    skip_rows
        Index of the first numeric row (lines before it, header included, are not
        data).
    has_header
        Whether the line just before the numeric block holds column names.
    """

    encoding: str | None = None
    delimiter: str | None = None
    decimal: str | None = None
    skip_rows: int | None = None
    has_header: bool | None = None


@dataclass(frozen=True)
class Table:
    """Numeric table read from a text file, with the settings that produced it.

    Attributes
    ----------
    data
        Array of shape ``(rows, columns)``.
    columns
        Column names from the header row, or ``None`` when there is none.
    settings
        The settings actually used; every field is filled.
    preamble
        The non-blank lines before the table (header excluded).
    """

    data: NDArray[np.float64]
    columns: tuple[str, ...] | None
    settings: ReadSettings
    preamble: tuple[str, ...]


def read_text(path: str | Path, settings: ReadSettings | None = None) -> Table:
    """Read a delimited text file.

    Parameters
    ----------
    path
        File to read.
    settings
        Overrides; every field left as ``None`` is detected.

    Returns
    -------
    Table
        The numeric block and the settings used.

    Raises
    ------
    UnreadableFile
        The file is missing, cannot be opened or cannot be decoded.
    NoNumericBlock
        No block of numeric rows with at least two columns was found.
    AmbiguousFormat
        The delimiter and decimal separator cannot be told apart.
    InvalidData
        The settings given are not valid.
    """
    settings = settings or ReadSettings()
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise UnreadableFile(
            f"Cannot read '{path}': {error.strerror or error}."
        ) from error
    text, encoding = decode(raw, settings.encoding, str(path))
    return parse_text(text, replace(settings, encoding=encoding), source=str(path))


def decode(raw: bytes, encoding: str | None, source: str) -> tuple[str, str]:
    """Decode ``raw`` and return the text and the name of the encoding used."""
    if encoding is not None:
        try:
            return raw.decode(encoding), encoding
        except (UnicodeDecodeError, LookupError) as error:
            raise UnreadableFile(
                f"Cannot decode '{source}' as {encoding}: {error}."
            ) from error
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    for candidate in _FALLBACK_ENCODINGS:
        try:
            return raw.decode(candidate), candidate
        except UnicodeDecodeError:
            continue
    raise UnreadableFile(f"Cannot decode '{source}'.")  # pragma: no cover


def parse_text(
    text: str, settings: ReadSettings | None = None, source: str = "text"
) -> Table:
    """Parse already decoded text. See :func:`read_text`."""
    settings = settings or ReadSettings()
    _validate(settings)
    lines = text.splitlines()
    delimiters = (settings.delimiter,) if settings.delimiter else DELIMITERS
    decimals = (settings.decimal,) if settings.decimal else DECIMALS

    best: tuple[int, int, int, int, str, str] | None = None
    for delimiter in delimiters:
        for decimal in decimals:
            if delimiter == decimal:
                continue
            found = _find_block(lines, delimiter, decimal, settings.skip_rows)
            if found is None:
                continue
            start, end, ncols = found
            score = sum(1 for line in lines[start:end] if line.strip()) * ncols
            if best is None or score > best[0]:
                best = (score, start, end, ncols, delimiter, decimal)
    if best is None:
        raise NoNumericBlock(
            f"No block of numeric rows with at least two columns was found in {source}."
        )

    _, start, end, ncols, delimiter, decimal = best
    block = [_split(line, delimiter) for line in lines[start:end] if line.strip()]
    _check_interruptions(
        lines, (start, end, ncols), (delimiter, decimal), settings.skip_rows, source
    )
    if delimiter == "," and settings.decimal is None:
        _check_comma_ambiguity(block, source)

    data = np.array(
        [[_to_float(token, decimal) for token in row] for row in block],
        dtype=np.float64,
    )
    header_index = _header_index(lines, start, delimiter, ncols, settings.has_header)
    columns = (
        tuple(_split(lines[header_index], delimiter))
        if header_index is not None
        else None
    )
    preamble_end = start if header_index is None else header_index
    return Table(
        data=data,
        columns=columns,
        settings=ReadSettings(
            encoding=settings.encoding or "utf-8",
            delimiter=delimiter,
            decimal=decimal,
            skip_rows=start,
            has_header=columns is not None,
        ),
        preamble=tuple(line for line in lines[:preamble_end] if line.strip()),
    )


def _validate(settings: ReadSettings) -> None:
    if settings.delimiter is not None and settings.delimiter not in DELIMITERS:
        raise InvalidData(
            f"Delimiter {settings.delimiter!r} is not one of {DELIMITERS!r}."
        )
    if settings.decimal is not None and settings.decimal not in DECIMALS:
        raise InvalidData(f"Decimal separator {settings.decimal!r} must be '.' or ','.")
    if settings.delimiter is not None and settings.delimiter == settings.decimal:
        raise InvalidData("The delimiter and the decimal separator cannot be the same.")
    if settings.skip_rows is not None and settings.skip_rows < 0:
        raise InvalidData("skip_rows cannot be negative.")


def _split(line: str, delimiter: str) -> list[str]:
    if delimiter == " ":
        return line.split()
    tokens = [token.strip() for token in line.split(delimiter)]
    if len(tokens) > 1 and tokens[-1] == "":  # trailing delimiter
        tokens.pop()
    return tokens


def _is_number(token: str, decimal: str) -> bool:
    if decimal == ",":
        if "." in token:
            return False
        token = token.replace(",", ".", 1)
    elif "," in token:
        return False
    return _NUMBER.match(token) is not None


def _to_float(token: str, decimal: str) -> float:
    if decimal == ",":
        token = token.replace(",", ".", 1)
    return float(token.replace("d", "e").replace("D", "e"))


def _numeric_columns(line: str, delimiter: str, decimal: str) -> int:
    """Return the column count when every cell of ``line`` is a number, else 0."""
    tokens = _split(line, delimiter)
    if len(tokens) >= 2 and all(_is_number(token, decimal) for token in tokens):
        return len(tokens)
    return 0


def _find_block(
    lines: list[str], delimiter: str, decimal: str, skip_rows: int | None
) -> tuple[int, int, int] | None:
    """Find the longest run of numeric rows; return ``(start, end, columns)``.

    Blank lines are ignored. ``end`` is exclusive. With ``skip_rows`` the block must
    start at the first non-blank line at or after that index.
    """
    first = skip_rows or 0
    indices = [i for i in range(first, len(lines)) if lines[i].strip()]

    best: tuple[int, int, int] | None = None
    best_rows = 0
    run_start = run_end = run_cols = rows = 0
    for index in indices:
        ncols = _numeric_columns(lines[index], delimiter, decimal)
        if ncols and rows and ncols == run_cols:
            rows += 1
            run_end = index + 1
            continue
        if rows > best_rows:
            best, best_rows = (run_start, run_end, run_cols), rows
        if skip_rows is not None and (rows or not ncols):
            return best  # the block must begin at the first line; it has just ended
        if ncols:
            rows, run_start, run_end, run_cols = 1, index, index + 1, ncols
        else:
            rows = 0
    if rows > best_rows:
        best = (run_start, run_end, run_cols)
    return best


def _raw_tokens(line: str, delimiter: str) -> list[str]:
    """Split a line keeping empty cells (``_split`` drops a trailing one)."""
    if delimiter == " ":
        return line.split()
    return [token.strip() for token in line.split(delimiter)]


def _interrupts(
    lines: list[str],
    index: int,
    step: int,
    ncols: int,
    delimiter: str,
    decimal: str,
) -> bool:
    """Whether the line next to the block is a data row broken by a bad cell.

    A line with no number at all (a header, a title, a footer) never interrupts. A line
    with some numbers does when it has the shape of a data row and starts with a number
    (``300;N/A``, ``300;``), or when more numeric rows lie beyond it, so that ignoring
    it would silently drop data.
    """
    tokens = _raw_tokens(lines[index], delimiter)
    if not any(_is_number(token, decimal) for token in tokens):
        return False
    data_shaped = len(tokens) == ncols or (
        len(tokens) == ncols + 1 and tokens[-1] == ""
    )
    if data_shaped and _is_number(tokens[0], decimal):
        return True
    beyond = range(index + step, len(lines) if step > 0 else -1, step)
    return any(_numeric_columns(lines[i], delimiter, decimal) == ncols for i in beyond)


def _check_interruptions(
    lines: list[str],
    block: tuple[int, int, int],
    formats: tuple[str, str],
    skip_rows: int | None,
    source: str,
) -> None:
    """Raise when a broken data row sits right next to the chosen block.

    Choosing the longest clean run would otherwise drop the rest of the data without a
    word. With ``skip_rows`` the user says where the data start, so only the end is
    checked.
    """
    start, end, ncols = block
    delimiter, decimal = formats
    neighbours = [
        (next((i for i in range(end, len(lines)) if lines[i].strip()), None), 1)
    ]
    if skip_rows is None:
        previous = next((i for i in range(start - 1, -1, -1) if lines[i].strip()), None)
        neighbours.append((previous, -1))
    for index, step in neighbours:
        if index is not None and _interrupts(
            lines, index, step, ncols, delimiter, decimal
        ):
            shown = lines[index].strip()
            if len(shown) > 60:
                shown = shown[:57] + "..."
            raise MalformedCell(
                f"Line {index + 1} of {source} ('{shown}') breaks the table of numbers "
                f"(lines {start + 1} to {end}, {ncols} columns): a cell is missing or "
                "is not a number. Fix or delete that line; otherwise part of the "
                "data would be dropped."
            )


def _check_comma_ambiguity(block: list[list[str]], source: str) -> None:
    """Refuse a comma-delimited block that could equally be decimal-comma pairs.

    ``1,5,2,5`` is either four integers or the two numbers 1.5 and 2.5 written with
    a decimal comma *and* a comma delimiter. Nothing in the file settles it.
    """
    ncols = len(block[0])
    if ncols < 4 or ncols % 2:
        return
    if all(_INTEGER.match(token) for row in block for token in row):
        raise AmbiguousFormat(
            f"The numbers in {source} are separated by commas and contain no decimal "
            "point, so a comma could be the delimiter or the decimal separator. Choose "
            "the delimiter and the decimal separator explicitly."
        )


def _header_index(
    lines: list[str], start: int, delimiter: str, ncols: int, has_header: bool | None
) -> int | None:
    """Index of the header line just before the block, if there is one."""
    if has_header is False:
        return None
    for index in range(start - 1, -1, -1):
        if not lines[index].strip():
            continue
        if len(_split(lines[index], delimiter)) == ncols:
            return index
        break
    if has_header:
        raise NoNumericBlock(
            "A header row was requested but none precedes the numeric block."
        )
    return None
