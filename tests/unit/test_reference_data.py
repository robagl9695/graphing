# SPDX-License-Identifier: GPL-3.0-or-later
"""Checks that the local reference outputs are present where the tests expect them."""

from pathlib import Path

import pytest

ORCA_DIR = Path(__file__).resolve().parents[1] / "reference" / "orca"


@pytest.mark.local_data
def test_orca_reference_cases_present() -> None:
    cases = sorted(p.name for p in ORCA_DIR.iterdir() if p.is_dir())
    assert cases == ["orca-421-tddft", "orca-601-freq", "orca-601-tddft"]
