# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the ORCA parsers (T2.5): synthetic texts, corpus files and local data."""

# ruff: noqa: E501  (rows of ORCA output are wider than the line limit)

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from graphing.core.errors import MalformedBlock, MissingBlock, UnreadableFile
from graphing.core.parsers import orca
from graphing.core.parsers.orca import (
    VERIFIED_FAMILIES,
    parse_orca_absorption,
    parse_orca_ir,
    read_orca_absorption,
    read_orca_ir,
)

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests" / "corpus"
REFERENCE = ROOT / "tests" / "reference" / "orca"

SEP = "-" * 77
HEADER_4X = f"""{SEP}
State   Energy    Wavelength  fosc         T2        TX        TY        TZ
        (cm-1)      (nm)                 (au**2)    (au)      (au)      (au)
{SEP}"""

# Electric block with fosc 0.2 / 0.3; the velocity block uses other values on purpose.
TEXT_4X = f"""                       Program Version 4.2.1 -  RELEASE  -

         ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS
{HEADER_4X}
   1   20000.0    500.0   0.200000000   1.00000   1.00000   0.00000   0.00000
   2   25000.0    400.0   0.300000000   1.00000   1.00000   0.00000   0.00000

{SEP}
         ABSORPTION SPECTRUM VIA TRANSITION VELOCITY DIPOLE MOMENTS
{SEP}
State   Energy    Wavelength   fosc        P2         PX        PY        PZ
{SEP}
   1   20000.0    500.0   0.900000000   1.00000   1.00000   0.00000   0.00000
   2   25000.0    400.0   0.800000000   1.00000   1.00000   0.00000   0.00000

{SEP}
                             CD SPECTRUM
{SEP}
State   Energy Wavelength       R         MX        MY        MZ
{SEP}
   1   20000.0    500.0     0.00000   0.10000   0.00000   0.00000
"""

TEXT_6X = """                       Program Version 6.0.1  -  RELEASE   -

                     ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS
----------------------------------------------------------------------------------------------------
     Transition      Energy     Energy  Wavelength fosc(D2)      D2        DX        DY        DZ
                      (eV)      (cm-1)    (nm)                 (au**2)    (au)      (au)      (au)
----------------------------------------------------------------------------------------------------
  0-2A  ->  1-4A    0.500000    4032.8  2479.7   0.000002000   0.00020   0.01000   0.00500  -0.00200
  0-2A  -> 10-2A    2.500000   20163.9   495.9   0.000120000   0.00100   0.00100   0.00100   0.00100

                     ABSORPTION SPECTRUM VIA TRANSITION VELOCITY DIPOLE MOMENTS
----------------------------------------------------------------------------------------------------
     Transition      Energy     Energy  Wavelength fosc(P2)      P2        PX        PY        PZ
----------------------------------------------------------------------------------------------------
  0-2A  ->  1-4A    0.500000    4032.8  2479.7   0.900000000   0.00020   0.01000   0.00500  -0.00200

                     CD SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS
----------------------------------------------------------------------------------------------------
     Transition      Energy     Energy  Wavelength    R         MX        MY        MZ
----------------------------------------------------------------------------------------------------
  0-2A  ->  1-4A    0.500000    4032.8  2479.7   0.700000000   0.00020   0.01000   0.00500  -0.00200
"""

TEXT_IR = """                       Program Version 6.0.1  -  RELEASE   -
IR SPECTRUM
-----------

 Mode   freq       eps      Int      T**2         TX        TY        TZ
       cm**-1   L/(mol*cm) km/mol    a.u.
----------------------------------------------------------------------------
  6:     30.00   0.000020    0.10  0.000200  ( 0.010000 -0.008000  0.004000)
  7:    800.00   0.039576  200.00  0.500000  ( 0.010000 -0.008000  0.004000)
  8:   1650.00   0.000000    0.00  0.000000  ( 0.000000  0.000000  0.000000)

* The epsilon (eps) is given for a Dirac delta lineshape.
"""


def with_line(text: str, old: str, new: str) -> str:
    assert old in text
    return text.replace(old, new, 1)


def test_layout_4x_values_and_other_blocks_are_ignored() -> None:
    result = parse_orca_absorption(TEXT_4X)
    assert result.layout == "4.x"
    assert result.version == "4.2.1"
    np.testing.assert_array_equal(result.energy_cm1, [20000.0, 25000.0])
    np.testing.assert_array_equal(result.wavelength_nm, [500.0, 400.0])
    # 0.2 and 0.3 are the electric block; the velocity block says 0.9 and 0.8.
    np.testing.assert_array_equal(result.fosc, [0.2, 0.3])


def test_layout_6x_labels_and_cd_blocks_are_ignored() -> None:
    result = parse_orca_absorption(TEXT_6X)
    assert result.layout == "6.x"
    np.testing.assert_array_equal(result.energy_cm1, [4032.8, 20163.9])
    np.testing.assert_array_equal(result.wavelength_nm, [2479.7, 495.9])
    np.testing.assert_allclose(result.fosc, [2.0e-06, 1.2e-04])


def test_block_at_the_end_of_the_file_without_blank_line() -> None:
    text = TEXT_6X.split("\n\n")[1]  # the absorption block, nothing after it
    assert len(parse_orca_absorption(text).fosc) == 2


def test_missing_absorption_block_names_the_block() -> None:
    with pytest.raises(
        MissingBlock, match="ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC"
    ):
        parse_orca_absorption("nothing here\n", source="run.out")


def test_velocity_block_alone_is_not_the_electric_block() -> None:
    velocity_only = (
        "         ABSORPTION SPECTRUM VIA TRANSITION VELOCITY DIPOLE MOMENTS\n"
    )
    with pytest.raises(MissingBlock):
        parse_orca_absorption(velocity_only)
    cd_only = "   CD SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS\n"
    with pytest.raises(MissingBlock):
        parse_orca_absorption(cd_only)


def test_missing_ir_block_names_the_block() -> None:
    with pytest.raises(MissingBlock, match="IR SPECTRUM"):
        parse_orca_ir(TEXT_4X)


def test_broken_row_in_the_middle_is_an_error_not_a_shorter_block() -> None:
    text = with_line(
        TEXT_4X, "2   25000.0    400.0   0.300", "2   25000.0x   400.0   0.300"
    )
    with pytest.raises(MalformedBlock, match=r"Line 9 of run.out"):
        parse_orca_absorption(text, source="run.out")


def test_broken_first_row_is_an_error() -> None:
    text = with_line(
        TEXT_4X, "1   20000.0    500.0   0.200", "1   20000.0    500.0   0.2oo"
    )
    with pytest.raises(MalformedBlock, match="not a valid row"):
        parse_orca_absorption(text)


def test_rows_of_different_shape_are_an_error() -> None:
    text = with_line(TEXT_6X, "  0-2A  -> 10-2A ", "  10-2A ")
    with pytest.raises(MalformedBlock):
        parse_orca_absorption(text)


def test_wavelength_that_disagrees_with_the_energy_is_an_error() -> None:
    text = with_line(TEXT_4X, "20000.0    500.0", "20000.0    450.0")
    with pytest.raises(MalformedBlock, match="does not match 20000.0 cm-1"):
        parse_orca_absorption(text)


def test_nine_numeric_fields_layout_is_not_recognised() -> None:
    text = with_line(
        TEXT_4X,
        "1.00000   0.00000   0.00000\n\n",
        "1.00000   0.00000   0.00000   9.0\n\n",
    )
    with pytest.raises(MalformedBlock):
        parse_orca_absorption(text)


def test_title_without_rows_is_an_error() -> None:
    text = f"         ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS\n{SEP}\n\n"
    with pytest.raises(MalformedBlock, match="has no rows"):
        parse_orca_absorption(text)


def test_families_are_unverified_until_the_corpus_has_a_real_file() -> None:
    result = parse_orca_absorption(TEXT_4X)
    assert any("not verified" in warning for warning in result.warnings)
    assert any("not verified" in warning for warning in parse_orca_ir(TEXT_IR).warnings)


def test_version_that_contradicts_the_layout_is_a_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = with_line(TEXT_4X, "Program Version 4.2.1", "Program Version 5.0.3")
    assert any("5.0.3" in warning for warning in parse_orca_absorption(text).warnings)
    monkeypatch.setattr(orca, "VERIFIED_FAMILIES", frozenset({"4.x"}))
    result = parse_orca_absorption(TEXT_4X)
    assert result.warnings == ()


def test_verified_families_equal_the_families_of_real_corpus_files() -> None:
    """AC4: the families claimed are exactly those with a real corpus file."""
    families = set()
    for sidecar in CORPUS.rglob("*.corpus.json"):
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        if data["reader"] == "orca" and data["kind"] == "program":
            families.add(f"{data['source']['version'].split('.')[0]}.x")
    assert set(VERIFIED_FAMILIES) == families


def test_ir_block_values() -> None:
    result = parse_orca_ir(TEXT_IR)
    assert result.mode_index == (6, 7, 8)
    np.testing.assert_array_equal(result.wavenumber_cm1, [30.0, 800.0, 1650.0])
    np.testing.assert_array_equal(result.intensity_km_mol, [0.10, 200.0, 0.0])
    np.testing.assert_array_equal(result.eps_orca, [0.000020, 0.039576, 0.0])
    assert result.version == "6.0.1"


def test_ir_broken_row_is_an_error() -> None:
    text = with_line(TEXT_IR, "800.00   0.039576", "800.00   0.0395x6")
    with pytest.raises(MalformedBlock, match="Line 9"):
        parse_orca_ir(text)


def test_ir_non_vibrational_version_warning() -> None:
    text = with_line(TEXT_IR, "Program Version 6.0.1", "Program Version 4.2.1")
    assert any("4.2.1" in warning for warning in parse_orca_ir(text).warnings)


def test_unreadable_file_is_named(tmp_path: Path) -> None:
    with pytest.raises(UnreadableFile, match="absent.out"):
        read_orca_absorption(tmp_path / "absent.out")
    with pytest.raises(UnreadableFile, match="absent.out"):
        read_orca_ir(tmp_path / "absent.out")


@pytest.mark.parametrize(
    "name", ["synthetic-3bands.out", "synthetic-shoulder.out", "synthetic-wave.out"]
)
def test_artificial_corpus_files_read(name: str) -> None:
    sidecar = json.loads(
        (CORPUS / "theoretical" / f"{name}.corpus.json").read_text(encoding="utf-8")
    )
    expected = sidecar["expect"]
    result = read_orca_absorption(CORPUS / "theoretical" / name)
    assert len(result.fosc) == expected["transitions"]
    first = [result.energy_cm1[0], result.wavelength_nm[0], result.fosc[0]]
    last = [result.energy_cm1[-1], result.wavelength_nm[-1], result.fosc[-1]]
    assert first == expected["first"]
    assert last == expected["last"]


# --- local data: unpublished real outputs, never committed (marker local_data) -----------


def local_expected(case: str) -> dict[str, Any]:
    """Expected values of a local case, kept with the unpublished files (X-04)."""
    path = REFERENCE.parent / "expected-values.json"
    return dict(json.loads(path.read_text(encoding="utf-8"))[case])


def case(name: str) -> dict[str, object]:
    return json.loads((REFERENCE / name / "case.json").read_text(encoding="utf-8"))


@pytest.mark.local_data
def test_local_orca_421_tddft() -> None:
    expected = local_expected("orca-421-tddft")
    result = read_orca_absorption(REFERENCE / "orca-421-tddft" / "orca-421-tddft.out")
    assert (result.layout, result.version) == ("4.x", "4.2.1")
    assert len(result.fosc) == expected["states"]
    assert result.energy_cm1[0] == expected["first_cm1"]
    assert result.wavelength_nm[0] == expected["first_nm"]
    assert result.fosc[0] == expected["first_fosc"]
    assert math.isclose(
        1e7 / result.energy_cm1[0], result.wavelength_nm[0], abs_tol=0.06
    )


@pytest.mark.local_data
def test_local_orca_601_tddft() -> None:
    expected = local_expected("orca-601-tddft")
    result = read_orca_absorption(REFERENCE / "orca-601-tddft" / "orca-601-tddft.out")
    assert (result.layout, result.version) == ("6.x", "6.0.1")
    assert len(result.fosc) == expected["states"]
    assert result.energy_cm1[0] == expected["first_cm1"]
    assert result.wavelength_nm[0] == expected["first_nm"]
    assert result.fosc[0] == expected["first_fosc"]


@pytest.mark.local_data
def test_local_orca_601_freq() -> None:
    expected = local_expected("orca-601-freq")
    result = read_orca_ir(REFERENCE / "orca-601-freq" / "orca-601-freq.out")
    assert len(result.mode_index) == expected["modes"]
    assert result.mode_index[0] == expected["first_index"]
    assert result.mode_index[-1] == expected["last_index"]
    first = [result.wavenumber_cm1[0], result.intensity_km_mol[0]]
    last = [result.wavenumber_cm1[-1], result.intensity_km_mol[-1]]
    assert first == expected["first"]
    assert last == expected["last"]
    strongest = int(np.argmax(result.intensity_km_mol))
    assert result.mode_index[strongest] == expected["strongest_index"]
    assert result.intensity_km_mol[strongest] == expected["strongest_km_mol"]
    assert not np.any(result.wavenumber_cm1 < 0)
    # ORCA defines eps = Int * 100/ln(10) / 219474.6313632 (checked on well-printed modes).
    strong = result.intensity_km_mol > 10
    expected = result.intensity_km_mol[strong] * (100 / math.log(10)) / 219474.6313632
    np.testing.assert_allclose(result.eps_orca[strong], expected, rtol=2e-3)
