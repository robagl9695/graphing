# SPDX-License-Identifier: GPL-3.0-or-later
"""Smoke test: the package imports and reports its version."""

import graphing


def test_version() -> None:
    assert graphing.__version__ == "0.1.0"
