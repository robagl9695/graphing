# SPDX-License-Identifier: GPL-3.0-or-later
"""T2.7: every format loads through graphing.core.io.load."""

from pathlib import Path

import numpy as np
import pytest

from graphing.core.constants import NM_TO_CM1
from graphing.core.data import CurveData, StickData
from graphing.core.errors import UnknownFormat
from graphing.core.io import LoadOptions, load, supported_formats
from graphing.core.readers.mapping import ColumnMapping
from graphing.core.spectrum import Origin, Technique
from graphing.core.units import Quantity, Unit

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
EXP, TH = Origin.EXPERIMENTAL, Origin.THEORETICAL
UV, IR = Technique.UV_VIS, Technique.IR

ORCA_IR = """                       Program Version 6.0.1  -  RELEASE   -
IR SPECTRUM
-----------

 Mode   freq       eps      Int      T**2         TX        TY        TZ
       cm**-1   L/(mol*cm) km/mol    a.u.
----------------------------------------------------------------------------
  6:     30.00   0.000020    0.10  0.000200  ( 0.010000 -0.008000  0.004000)
  7:    800.00   0.039576  200.00  0.500000  ( 0.010000 -0.008000  0.004000)

* The epsilon (eps) is given for a Dirac delta lineshape.
"""


def test_text_table_as_experimental_gives_curves() -> None:
    (s,) = load(CORPUS / "synthetic" / "uvvis-tab-header.txt", UV, EXP)
    assert isinstance(s.data, CurveData)
    assert s.origin is EXP and s.technique is UV


def test_multicolumn_csv_gives_one_spectrum_per_column() -> None:
    spectra = load(CORPUS / "synthetic" / "uvvis-multicolumn.csv", UV, EXP)
    assert len(spectra) == 4


@pytest.mark.parametrize("suffix", [".xlsx", ".ods"])
def test_spreadsheet_loads(suffix: str) -> None:
    spectra = load(CORPUS / "synthetic" / f"uvvis-merged-header{suffix}", UV, EXP)
    assert spectra and isinstance(spectra[0].data, CurveData)


def test_instrument_ir_export_loads() -> None:
    mapping = ColumnMapping(
        x_column=0,
        y_columns=(1,),
        x_quantity=Quantity.WAVENUMBER,
        x_unit=Unit.CM1,
        y_quantity=Quantity.TRANSMITTANCE,
        technique=IR,
        origin=EXP,
    )
    path = CORPUS / "experimental" / "hydroquinone-ir-2023-09-04.asc"
    spectra = load(path, IR, EXP, options=LoadOptions(mapping=mapping))
    assert isinstance(spectra[0].data, CurveData)


def test_wrong_origin_is_read_as_declared_without_error() -> None:
    path = CORPUS / "synthetic" / "uvvis-tab-header.txt"
    (as_theory,) = load(path, UV, TH)
    assert isinstance(as_theory.data, StickData)
    assert as_theory.origin is TH
    (as_curve,) = load(path, UV, EXP)
    np.testing.assert_array_equal(as_theory.data.x, as_curve.data.x)


def test_theoretical_table_keeps_repeated_positions(tmp_path: Path) -> None:
    f = tmp_path / "lines.csv"
    f.write_text("Wavelength,f\n300,0.1\n250,0.2\n300,0.3\n", encoding="utf-8")
    mapping = ColumnMapping(
        x_column=0,
        y_columns=(1,),
        x_quantity=Quantity.WAVELENGTH,
        x_unit=Unit.NM,
        y_quantity=Quantity.OSCILLATOR_STRENGTH,
        technique=UV,
        origin=TH,
    )
    (s,) = load(f, UV, TH, options=LoadOptions(mapping=mapping))
    assert isinstance(s.data, StickData)
    np.testing.assert_array_equal(s.data.x, [300, 250, 300])


def test_explicit_mapping_and_declared_origin_win(tmp_path: Path) -> None:
    f = tmp_path / "t.csv"
    f.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    mapping = ColumnMapping(
        x_column=0,
        y_columns=(1,),
        x_quantity=Quantity.WAVELENGTH,
        x_unit=Unit.NM,
        y_quantity=Quantity.ABSORBANCE,
        technique=IR,
        origin=EXP,
    )
    (s,) = load(f, UV, TH, options=LoadOptions(mapping=mapping))
    assert s.technique is UV and s.origin is TH


def test_orca_uvvis_sticks_in_nm_with_labels() -> None:
    (s,) = load(CORPUS / "theoretical" / "synthetic-3bands.out", UV, TH, "orca")
    assert isinstance(s.data, StickData)
    assert s.data.x_quantity is Quantity.WAVELENGTH and s.data.x_unit is Unit.NM
    np.testing.assert_allclose(NM_TO_CM1 / s.data.x, [20000, 25000, 30000])
    assert s.data.line_labels() == ("1", "2", "3")
    assert s.metadata["program"] == "ORCA"


def test_orca_ir_modes_labelled_by_mode_number(tmp_path: Path) -> None:
    f = tmp_path / "run.out"
    f.write_text(ORCA_IR, encoding="utf-8")
    (s,) = load(f, IR, TH, "orca")
    assert s.data.x_unit is Unit.CM1 and s.data.y_unit is Unit.KM_MOL
    assert s.data.labels == ("6", "7")


def test_turbomole_exspectrum() -> None:
    (s,) = load(
        CORPUS / "theoretical" / "artificial.exspectrum", UV, TH, "turbomole-exspectrum"
    )
    assert s.data.labels[0] == "1 a"
    np.testing.assert_allclose(NM_TO_CM1 / s.data.x[2], 30000.0)


def test_turbomole_vibspectrum_flags_imaginary_mode() -> None:
    (s,) = load(
        CORPUS / "theoretical" / "imaginary-mode.vibspectrum",
        IR,
        TH,
        "turbomole-vibspectrum",
    )
    assert s.data.x.size == 14
    assert s.data.x[6] == pytest.approx(-284.71)
    assert s.metadata["imaginary_modes"] == "7"


def test_program_output_ignores_declared_origin() -> None:
    (s,) = load(CORPUS / "theoretical" / "synthetic-3bands.out", UV, EXP, "orca")
    assert s.origin is TH


def test_program_output_needs_a_format() -> None:
    with pytest.raises(UnknownFormat, match="Name the format"):
        load(CORPUS / "theoretical" / "synthetic-3bands.out", UV, TH)


def test_unknown_format_id_lists_known_ones() -> None:
    with pytest.raises(UnknownFormat, match="orca"):
        load(CORPUS / "theoretical" / "synthetic-3bands.out", UV, TH, "gaussian")


def test_supported_formats_come_from_the_registry() -> None:
    ids = [f.id for f in supported_formats()]
    assert ids == [
        "table-text",
        "table-sheet",
        "orca",
        "turbomole-exspectrum",
        "turbomole-escf",
        "turbomole-vibspectrum",
    ]
