# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared test configuration.

Tests marked ``local_data`` need unpublished files in ``tests/reference/``.
Those files stay on the maintainer's disk (CLAUDE.md section 8.4), so the
tests are skipped with an explicit reason when the folder is missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REFERENCE_DIR = Path(__file__).resolve().parent / "reference"


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip ``local_data`` tests when ``tests/reference/`` is absent."""
    if REFERENCE_DIR.is_dir():
        return
    reason = (
        "tests/reference/ not found: unpublished local data, "
        "an extra check that is not required to pass"
    )
    skip_marker = pytest.mark.skip(reason=reason)
    for item in items:
        if item.get_closest_marker("local_data") is not None:
            item.add_marker(skip_marker)
