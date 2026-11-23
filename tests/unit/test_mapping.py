# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the column mapping (T2.3)."""

from __future__ import annotations

import numpy as np
import pytest

from graphing.core.data import CurveData
from graphing.core.errors import InvalidMapping, NonNumericCells
from graphing.core.readers.mapping import (
    ColumnMapping,
    build_spectra,
    suggest_mapping,
)
from graphing.core.readers.text import Table, parse_text
from graphing.core.spectrum import Origin, Technique
from graphing.core.units import Quantity, Unit

TEXT = (
    "Wavelength (nm);Abs A;Abs B;Abs C\n"
    "300;0.1;0.2;0.3\n310;0.4;0.5;0.6\n320;0.7;0.8;0.9\n"
)


def table_from(text: str = TEXT) -> Table:
    return parse_text(text.replace(".", ","), source="fixture.csv")


def mapping(**changes: object) -> ColumnMapping:
    base: dict[str, object] = {
        "x_column": 0,
        "y_columns": (1, 2, 3),
        "x_quantity": Quantity.WAVELENGTH,
        "x_unit": Unit.NM,
        "y_quantity": Quantity.ABSORBANCE,
        "technique": Technique.UV_VIS,
        "origin": Origin.EXPERIMENTAL,
    }
    base.update(changes)
    return ColumnMapping(**base)  # type: ignore[arg-type]


def test_n_y_columns_give_n_spectra_sharing_x() -> None:
    spectra = build_spectra(table_from(), mapping(), source="fixture.csv")
    assert [s.name for s in spectra] == ["Abs A", "Abs B", "Abs C"]
    for spectrum in spectra:
        assert isinstance(spectrum.data, CurveData)
        np.testing.assert_array_equal(spectrum.data.x, [300.0, 310.0, 320.0])
        assert spectrum.technique is Technique.UV_VIS
        assert spectrum.origin is Origin.EXPERIMENTAL
        assert spectrum.data.y_unit is Unit.DIMENSIONLESS
        assert spectrum.metadata["source"] == "fixture.csv"
    np.testing.assert_array_equal(spectra[1].data.y, [0.2, 0.5, 0.8])
    assert spectra[0].metadata["column"] == "2"


def test_single_y_column_and_unnamed_columns() -> None:
    table = table_from("300;0,1\n310;0,2\n")
    (spectrum,) = build_spectra(table, mapping(y_columns=(1,)))
    assert spectrum.name == "Column 2"


def test_x_may_be_any_column() -> None:
    table = table_from("0,1;300\n0,2;310\n")
    (spectrum,) = build_spectra(table, mapping(x_column=1, y_columns=(0,)))
    np.testing.assert_array_equal(spectrum.data.x, [300.0, 310.0])
    np.testing.assert_array_equal(spectrum.data.y, [0.1, 0.2])


def test_non_numeric_cells_are_reported_with_row_numbers() -> None:
    table = table_from("Wavelength;Abs\n300;0,1\n310;0,2\n320;0,3\n330;0,4\n")
    data = table.data.copy()
    data[1, 1] = np.nan
    data[3, 1] = np.inf
    broken = Table(
        data=data, columns=table.columns, settings=table.settings, preamble=()
    )
    with pytest.raises(
        NonNumericCells, match=r"Column 2 \(Abs\).*row\(s\) 2, 4.*line 2"
    ):
        build_spectra(broken, mapping(y_columns=(1,)))


def test_non_numeric_in_unchosen_column_is_ignored() -> None:
    table = table_from()
    data = table.data.copy()
    data[0, 3] = np.nan
    ok = Table(data=data, columns=table.columns, settings=table.settings, preamble=())
    assert len(build_spectra(ok, mapping(y_columns=(1, 2)))) == 2


def test_descending_x_is_reordered_and_recorded() -> None:
    table = table_from("4000;0,9\n3000;0,5\n2000;0,1\n")
    (spectrum,) = build_spectra(
        table,
        mapping(
            y_columns=(1,),
            x_quantity=Quantity.WAVENUMBER,
            x_unit=Unit.CM1,
            y_quantity=Quantity.TRANSMITTANCE,
            technique=Technique.IR,
        ),
    )
    np.testing.assert_array_equal(spectrum.data.x, [2000.0, 3000.0, 4000.0])
    np.testing.assert_array_equal(spectrum.data.y, [0.1, 0.5, 0.9])
    assert spectrum.metadata["x_reordered"] == "yes"


def test_repeated_x_is_an_error_not_silently_fixed() -> None:
    table = table_from("300;0,1\n300;0,2\n310;0,3\n")
    with pytest.raises(InvalidMapping, match="repeats the value 300"):
        build_spectra(table, mapping(y_columns=(1,)))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"y_columns": ()}, "at least one y column"),
        ({"y_columns": (1, 9)}, "Column 10 does not exist"),
        ({"x_column": -1}, "Column 0 does not exist"),
        ({"y_columns": (0, 1)}, "used twice"),
        ({"y_columns": (1, 1)}, "used twice"),
        ({"x_quantity": Quantity.ABSORBANCE}, "cannot be the x quantity"),
    ],
)
def test_invalid_mappings_are_named(changes: dict[str, object], message: str) -> None:
    with pytest.raises(InvalidMapping, match=message):
        build_spectra(table_from(), mapping(**changes))


def test_preamble_goes_to_metadata() -> None:
    table = parse_text("Instrument X\nWavelength;Abs\n300;1\n310;2\n")
    (spectrum,) = build_spectra(table, mapping(y_columns=(1,)))
    assert spectrum.metadata["preamble"] == "Instrument X"


def test_suggestion_default_and_header_hints() -> None:
    suggestion = suggest_mapping(table_from())
    assert suggestion.x_column == 0
    assert suggestion.y_columns == (1, 2, 3)
    assert suggestion.x_quantity is Quantity.WAVELENGTH
    assert suggestion.x_unit is Unit.NM
    assert suggestion.y_quantity is Quantity.ABSORBANCE


@pytest.mark.parametrize(
    ("header", "x_quantity", "y_quantity"),
    [
        ("Wavenumber (cm-1);%T", Quantity.WAVENUMBER, Quantity.TRANSMITTANCE),
        (
            "Número de onda (cm⁻¹);Transmitancia",
            Quantity.WAVENUMBER,
            Quantity.TRANSMITTANCE,
        ),
        ("Energy (eV);ε", Quantity.ENERGY, Quantity.MOLAR_ABSORPTIVITY),
        ("Longitud de onda;Intensidad", Quantity.WAVELENGTH, Quantity.INTENSITY),
    ],
)
def test_header_hints(header: str, x_quantity: Quantity, y_quantity: Quantity) -> None:
    suggestion = suggest_mapping(parse_text(header + "\n1;2\n3;4\n"))
    assert suggestion.x_quantity is x_quantity
    assert suggestion.y_quantity is y_quantity


def test_no_hint_when_headers_say_nothing_or_disagree() -> None:
    assert suggest_mapping(parse_text("1 2\n3 4\n")).x_quantity is None
    mixed = parse_text("Wavelength Abs %T\n1 2 3\n4 5 6\n")
    assert mixed.columns is not None
    assert suggest_mapping(mixed).y_quantity is None


def test_suggestion_is_never_applied_without_confirmation() -> None:
    suggestion = suggest_mapping(table_from())
    # build_spectra takes only a ColumnMapping; a suggestion has no technique.
    with pytest.raises(AttributeError):
        _ = suggestion.technique  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        suggestion.to_mapping()  # type: ignore[call-arg]
    confirmed = suggestion.to_mapping(Technique.UV_VIS, Origin.EXPERIMENTAL)
    assert confirmed.technique is Technique.UV_VIS
    assert len(build_spectra(table_from(), confirmed)) == 3


def test_confirming_without_quantities_requires_the_caller_to_choose() -> None:
    suggestion = suggest_mapping(parse_text("1 2\n3 4\n"))
    with pytest.raises(InvalidMapping, match="choose them"):
        suggestion.to_mapping(Technique.IR, Origin.EXPERIMENTAL)
    mapping_ = suggestion.to_mapping(
        Technique.IR,
        Origin.EXPERIMENTAL,
        x_quantity=Quantity.WAVENUMBER,
        y_quantity=Quantity.TRANSMITTANCE,
    )
    assert mapping_.x_unit is Unit.CM1
