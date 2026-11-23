# SPDX-License-Identifier: GPL-3.0-or-later
"""The figure model: project, canvas, panel, axes and layers (architecture §4).

Value objects (``Broadening``, ``Style``, axes, ``LayerArrangement``) are frozen.
Containers (``Layer``, ``Panel``, ``Inset``, ``Canvas``, ``Project``) are mutable and
are changed only through :mod:`graphing.core.operations`.
"""

from graphing.core.model.axes import (
    NORMALISED_OVERLAP,
    OVERLAP,
    STACKED,
    LayerArrangement,
    Scale,
    Side,
    XAxis,
    YAxis,
)
from graphing.core.model.broadening import Broadening, LineShape
from graphing.core.model.canvas import SCHEMA_VERSION, Canvas, Cell, Grid, Project
from graphing.core.model.panel import FreeInset, Inset, Layer, Panel, ZoomInset
from graphing.core.model.style import PALETTE, LineStyle, Style

__all__ = [
    "NORMALISED_OVERLAP",
    "OVERLAP",
    "PALETTE",
    "SCHEMA_VERSION",
    "STACKED",
    "Broadening",
    "Canvas",
    "Cell",
    "FreeInset",
    "Grid",
    "Inset",
    "Layer",
    "LayerArrangement",
    "LineShape",
    "LineStyle",
    "Panel",
    "Project",
    "Scale",
    "Side",
    "Style",
    "XAxis",
    "YAxis",
    "ZoomInset",
]
