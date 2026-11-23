# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests of the Turbomole parsers (T2.6): synthetic texts, corpus files, local data."""

# ruff: noqa: E501  (rows of Turbomole output are wider than the line limit)

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from graphing.core.errors import MalformedBlock, MissingBlock, UnreadableFile
from graphing.core.parsers.turbomole import (
    VERIFIED_FAMILIES,
    parse_turbomole_escf,
    parse_turbomole_exspectrum,
    parse_turbomole_vibspectrum,
    read_turbomole_escf,
    read_turbomole_exspectrum,
    read_turbomole_vibspectrum,
)

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests" / "corpus"
REFERENCE = ROOT / "tests" / "reference"

EXSPECTRUM = """# Excitation spectrum ; written at 2026-11-18 00:00:00
#     Exc.     energy (Eh)   energy (eV)   energy (cm-1)   energy (nm)     Osc.(vel)      Osc.(len)
       1 a        0.082014       2.23172       18000.000       555.556     0.00000500     0.00000300
       2 a        0.113908       3.09960       25000.000       400.000     0.02500000     0.02400000
       3 a        0.136690       3.71953       30000.000       333.333     0.10000000     0.12000000
"""

ESCF = """ escf (node01.example.org) : TURBOMOLE V7.3.1 () 1 Jan 2026 at 00:00:00

                         1 singlet a excitation

 Total energy:                           -500.1234567890123

 Excitation energy / nm:                  555.5517451869672

 Excitation energy / cm^(-1):             18000.12345678901

 Oscillator strength:

    velocity representation:             0.5000000000000000E-05

    length representation:               0.3000000000000000E-05

    mixed representation:                0.4000000000000000E-05

 Rotatory strength:

    velocity representation:             0.2000000000000000E-06
    length representation:               0.9900000000000000E-01

                         2 singlet a excitation

 Excitation energy / nm:                  400.0000000

 Excitation energy / cm^(-1):             25000.0000

 Oscillator strength:

    velocity representation:             0.2500000000000000E-01

    length representation:               0.2400000000000000E-01

 Rotatory strength:

    velocity representation:             0.1E-06

 SUMMARY OF EXCITATION ENERGIES AND DIPOLE OSCILLATOR STRENGTHS (velocity/length):
  1 singlet a   18000.12   0.00000   0.00000
"""

VIBSPECTRUM = """$vibrational spectrum
#  mode     symmetry     wave number   IR intensity    selection rules
#                         cm**(-1)        km/mol         IR     RAMAN
     1                       -0.00         0.00000        -       -
     2                        0.00         0.00000        -       -
     7        a            -284.71        18.40000       YES     YES
     8        a             612.30        95.60000       YES     YES
     9        b             848.55         4.20000       YES      -
    10        a            1043.12         0.00000        -      YES
$end
"""


def with_line(text: str, old: str, new: str) -> str:
    assert old in text
    return text.replace(old, new, 1)


# --- exspectrum ---------------------------------------------------------------------


def test_exspectrum_values_use_the_length_representation() -> None:
    result = parse_turbomole_exspectrum(EXSPECTRUM)
    np.testing.assert_array_equal(result.energy_cm1, [18000.0, 25000.0, 30000.0])
    np.testing.assert_array_equal(result.wavelength_nm, [555.556, 400.0, 333.333])
    # Osc.(len) is the last column; Osc.(vel) differs on purpose in the third row.
    np.testing.assert_array_equal(result.fosc, [3e-06, 0.024, 0.12])
    assert result.labels == ("1 a", "2 a", "3 a")
    assert result.source == "exspectrum"


def test_exspectrum_with_other_title_text_is_accepted() -> None:
    text = with_line(
        EXSPECTRUM,
        "# Excitation spectrum ;",
        "# Excitation spectrum Ni2 geom optimization;",
    )
    assert len(parse_turbomole_exspectrum(text).fosc) == 3


def test_exspectrum_without_header_is_missing_block() -> None:
    with pytest.raises(MissingBlock, match="exspectrum header"):
        parse_turbomole_exspectrum("1 a 0.1 2.0 3.0 4.0 5.0 6.0\n", source="x")


def test_exspectrum_broken_row_is_an_error_with_its_line() -> None:
    text = with_line(EXSPECTRUM, "25000.000", "25000.00x")
    with pytest.raises(MalformedBlock, match=r"Line 4 of run"):
        parse_turbomole_exspectrum(text, source="run")


def test_exspectrum_row_with_a_missing_column_is_an_error() -> None:
    text = with_line(EXSPECTRUM, "     0.10000000     0.12000000", "     0.12000000")
    with pytest.raises(MalformedBlock, match="Line 5"):
        parse_turbomole_exspectrum(text)


def test_exspectrum_wavelength_that_disagrees_with_energy_is_an_error() -> None:
    text = with_line(EXSPECTRUM, "400.000", "410.000")
    with pytest.raises(MalformedBlock, match="does not match 25000"):
        parse_turbomole_exspectrum(text)


def test_exspectrum_header_without_rows_is_an_error() -> None:
    header_only = "\n".join(EXSPECTRUM.splitlines()[:2]) + "\n"
    with pytest.raises(MalformedBlock, match="no rows"):
        parse_turbomole_exspectrum(header_only)


# --- escf.out -----------------------------------------------------------------------


def test_escf_paragraphs_full_precision_and_decoys_ignored() -> None:
    result = parse_turbomole_escf(ESCF)
    np.testing.assert_array_equal(result.energy_cm1, [18000.12345678901, 25000.0])
    # Length is under "Oscillator strength:"; the one under "Rotatory strength:" is 0.099.
    np.testing.assert_array_equal(result.fosc, [0.3e-05, 0.024])
    np.testing.assert_array_equal(result.wavelength_nm, [555.5517451869672, 400.0])
    assert result.labels == ("1 singlet a", "2 singlet a")
    assert result.version == "7.3.1"
    assert result.source == "escf.out"


def test_escf_without_paragraphs_is_missing_block() -> None:
    with pytest.raises(MissingBlock, match="excitation"):
        parse_turbomole_escf("escf finished\n")


def test_escf_paragraph_without_oscillator_strength_is_an_error() -> None:
    text = with_line(
        ESCF, "    length representation:               0.3000000000000000E-05\n", ""
    )
    with pytest.raises(MalformedBlock, match="state '1 singlet a'"):
        parse_turbomole_escf(text)


def test_escf_broken_number_is_an_error() -> None:
    text = with_line(ESCF, "18000.12345678901", "18000.12x45678901")
    with pytest.raises(MalformedBlock, match="cannot be read"):
        parse_turbomole_escf(text)


def test_escf_wavelength_is_none_when_not_printed() -> None:
    text = with_line(
        ESCF, " Excitation energy / nm:                  400.0000000\n", ""
    )
    assert parse_turbomole_escf(text).wavelength_nm is None


# --- vibspectrum --------------------------------------------------------------------


def test_vibspectrum_returns_every_mode_with_flags() -> None:
    result = parse_turbomole_vibspectrum(VIBSPECTRUM)
    assert result.mode_index == (1, 2, 7, 8, 9, 10)
    assert result.symmetry == ("-", "-", "a", "a", "b", "a")
    np.testing.assert_array_equal(
        result.wavenumber_cm1, [-0.0, 0.0, -284.71, 612.3, 848.55, 1043.12]
    )
    np.testing.assert_array_equal(
        result.intensity_km_mol, [0.0, 0.0, 18.4, 95.6, 4.2, 0.0]
    )
    assert result.ir_active.tolist() == [False, False, True, True, True, False]
    assert result.raman_active.tolist() == [False, False, True, True, False, True]


def test_imaginary_modes_are_flagged_not_dropped() -> None:
    result = parse_turbomole_vibspectrum(VIBSPECTRUM)
    assert result.imaginary.tolist() == [False, False, True, False, False, False]
    assert result.wavenumber_cm1[result.imaginary].tolist() == [-284.71]
    # "-0.00" is a negative zero, not an imaginary frequency.
    assert not result.imaginary[0]


def test_vibspectrum_without_section_is_missing_block() -> None:
    with pytest.raises(MissingBlock, match=r"\$vibrational spectrum"):
        parse_turbomole_vibspectrum("nothing here\n")


def test_vibspectrum_broken_row_is_an_error_with_its_line() -> None:
    text = with_line(VIBSPECTRUM, "612.30", "612.3x")
    with pytest.raises(MalformedBlock, match="Line 7 of run"):
        parse_turbomole_vibspectrum(text, source="run")


def test_vibspectrum_unknown_flag_is_an_error() -> None:
    text = with_line(
        VIBSPECTRUM, "95.60000       YES     YES", "95.60000       MAYBE   YES"
    )
    with pytest.raises(MalformedBlock, match="Line 7"):
        parse_turbomole_vibspectrum(text)


def test_vibspectrum_without_end_looks_truncated() -> None:
    text = VIBSPECTRUM.replace("$end\n", "")
    with pytest.raises(MalformedBlock, match="no '\\$end'"):
        parse_turbomole_vibspectrum(text)


def test_vibspectrum_section_without_rows_is_an_error() -> None:
    with pytest.raises(MalformedBlock, match="no rows"):
        parse_turbomole_vibspectrum("$vibrational spectrum\n#  header\n$end\n")


# --- common ------------------------------------------------------------------------


def test_family_is_unverified_until_the_corpus_has_a_real_file() -> None:
    assert any(
        "not verified" in w for w in parse_turbomole_exspectrum(EXSPECTRUM).warnings
    )
    assert any(
        "not verified" in w for w in parse_turbomole_vibspectrum(VIBSPECTRUM).warnings
    )


def test_verified_families_equal_the_families_of_real_corpus_files() -> None:
    families = set()
    for sidecar in CORPUS.rglob("*.corpus.json"):
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        if data["reader"].startswith("turbomole") and data["kind"] == "program":
            families.add(f"{data['source']['version'].split('.')[0]}.x")
    assert set(VERIFIED_FAMILIES) == families


def test_unreadable_file_is_named(tmp_path: Path) -> None:
    for reader in (
        read_turbomole_exspectrum,
        read_turbomole_escf,
        read_turbomole_vibspectrum,
    ):
        with pytest.raises(UnreadableFile, match="absent"):
            reader(tmp_path / "absent")


def test_artificial_imaginary_mode_file_in_the_corpus() -> None:
    path = CORPUS / "theoretical" / "imaginary-mode.vibspectrum"
    expected = json.loads(
        (path.with_name(path.name + ".corpus.json")).read_text(encoding="utf-8")
    )["expect"]
    result = read_turbomole_vibspectrum(path)
    assert len(result.mode_index) == expected["modes"]
    assert (
        result.wavenumber_cm1[result.imaginary].tolist()
        == expected["negative_wavenumbers"]
    )


# --- local data: unpublished real outputs, never committed (marker local_data) ------

CRQ = REFERENCE / "turbomole" / "crq200"
MEETING = REFERENCE / "meeting-20260918"


def local_expected(case: str) -> dict[str, Any]:
    """Expected values of a local case, kept with the unpublished files (X-04)."""
    data = json.loads((REFERENCE / "expected-values.json").read_text(encoding="utf-8"))
    return dict(data[case])


def dat_rows(path: Path) -> list[list[str]]:
    return [
        line.split()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


@pytest.mark.local_data
def test_local_crq200_exspectrum_and_escf_agree() -> None:
    expected = local_expected("crq200")
    ex = read_turbomole_exspectrum(CRQ / "exspectrum")
    escf = read_turbomole_escf(CRQ / "escf.out")
    assert len(ex.fosc) == len(escf.fosc) == expected["exspectrum_states"]
    first = [ex.energy_cm1[0], ex.wavelength_nm[0], ex.fosc[0]]  # type: ignore[index]
    last = [ex.energy_cm1[-1], ex.wavelength_nm[-1], ex.fosc[-1]]  # type: ignore[index]
    assert first == expected["exspectrum_first"]
    assert last == expected["exspectrum_last"]
    assert escf.energy_cm1[0] == expected["escf_first_cm1"]
    assert escf.fosc[0] == expected["escf_first_fosc"]
    assert escf.version == expected["escf_version"]
    np.testing.assert_allclose(escf.energy_cm1, ex.energy_cm1, atol=6e-4)
    np.testing.assert_allclose(escf.fosc, ex.fosc, rtol=1e-3, atol=6e-9)


@pytest.mark.local_data
def test_local_crq200_vibspectrum() -> None:
    expected = local_expected("crq200")
    result = read_turbomole_vibspectrum(CRQ / "vibspectrum")
    assert len(result.mode_index) == expected["vib_modes"]
    active = result.ir_active
    assert int(active.sum()) == expected["vib_ir_active"]
    assert (
        result.mode_index[int(np.argmax(active))] == expected["vib_first_active_index"]
    )
    assert result.mode_index[-1] == expected["vib_last_index"]
    wavenumber = result.wavenumber_cm1[active]
    intensity = result.intensity_km_mol[active]
    assert [wavenumber[0], intensity[0]] == expected["vib_first_active"]
    assert [wavenumber[-1], intensity[-1]] == expected["vib_last_active"]
    assert not result.imaginary.any()


@pytest.mark.local_data
def test_local_meeting_exspectrum_matches_qclab_utilities() -> None:
    result = read_turbomole_exspectrum(MEETING / "exspectrum")
    rows = dat_rows(MEETING / "exspectrum.transitions.dat")
    assert (
        len(result.fosc) == len(rows) == local_expected("meeting")["exspectrum_states"]
    )
    cm1 = np.array([float(row[2]) for row in rows])
    fosc = np.array([float(row[4]) for row in rows])
    np.testing.assert_allclose(result.energy_cm1, cm1, rtol=1e-9)
    np.testing.assert_allclose(result.fosc, fosc, rtol=1e-9)


@pytest.mark.local_data
def test_local_meeting_vibspectrum_matches_qclab_utilities() -> None:
    result = read_turbomole_vibspectrum(MEETING / "vibspectrum")
    rows = dat_rows(MEETING / "vibspectrum.modes.dat")
    active = result.ir_active
    assert int(active.sum()) == len(rows) == local_expected("meeting")["vib_ir_active"]
    np.testing.assert_allclose(
        result.wavenumber_cm1[active], [float(r[2]) for r in rows], rtol=1e-9
    )
    np.testing.assert_allclose(
        result.intensity_km_mol[active], [float(r[3]) for r in rows], rtol=1e-9
    )
    assert [str(int(float(r[0]))) for r in rows] == [
        str(i) for i in np.array(result.mode_index)[active]
    ]
