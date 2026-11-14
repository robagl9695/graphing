# SPDX-License-Identifier: GPL-3.0-or-later
"""graphing: plot and analyse UV-Vis and IR spectra."""

from importlib.metadata import PackageNotFoundError, version

try:
    # The version lives only in pyproject.toml (CLAUDE.md section 9).
    __version__ = version("graphing")
except PackageNotFoundError:  # pragma: no cover - not installed
    __version__ = "0+unknown"

__all__ = ["__version__"]
