# SPDX-License-Identifier: GPL-3.0-or-later
"""Canvas layout and project (architecture §4.6, §4.7)."""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import KW_ONLY, dataclass, field
from types import MappingProxyType

from graphing.core.errors import GridOverlap, InvalidData, NonPositiveValue
from graphing.core.model.panel import Panel, new_id

# Version of the project-file schema; independent of the app version (CLAUDE §9).
SCHEMA_VERSION: int = 1

DEFAULT_CANVAS_SIZE_CM: tuple[float, float] = (16.0, 12.0)


def _positive_tuple(values: Sequence[float], what: str) -> tuple[float, ...]:
    result = tuple(float(v) for v in values)
    if not result:
        raise InvalidData(f"{what} needs at least one value")
    for v in result:
        if not (math.isfinite(v) and v > 0):
            raise NonPositiveValue(f"{what} must all be greater than zero; got {v!r}")
    return result


@dataclass(frozen=True)
class Cell:
    """A rectangle of grid slots holding a panel or a nested grid."""

    row: int
    column: int
    _: KW_ONLY
    content: Panel | Grid
    row_span: int = 1
    column_span: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.content, (Panel, Grid)):
            raise InvalidData("every cell must hold a panel or a grid")
        if self.row < 0 or self.column < 0:
            raise InvalidData("cell row and column start at 0")
        if self.row_span < 1 or self.column_span < 1:
            raise InvalidData("cell spans must be at least 1")


@dataclass(frozen=True)
class Grid:
    """A proportional grid of cells (G1: inside and not overlapping; G2: no blanks).

    Raises
    ------
    NonPositiveValue
        A width or height is not finite and positive.
    InvalidData
        A cell lies outside the grid, or one panel appears twice.
    GridOverlap
        Two cells share a slot.
    """

    column_widths: tuple[float, ...]
    row_heights: tuple[float, ...]
    cells: tuple[Cell, ...]

    def __post_init__(self) -> None:
        widths = _positive_tuple(self.column_widths, "column widths")
        heights = _positive_tuple(self.row_heights, "row heights")
        cells = tuple(self.cells)
        if not cells:
            raise InvalidData("a grid needs at least one cell")
        taken: dict[tuple[int, int], int] = {}
        for index, cell in enumerate(cells):
            if not isinstance(cell, Cell):
                raise InvalidData("grid cells must be Cell objects")
            if cell.row + cell.row_span > len(
                heights
            ) or cell.column + cell.column_span > len(widths):
                raise InvalidData(
                    f"cell {index} at ({cell.row}, {cell.column}) goes outside the "
                    f"{len(heights)} × {len(widths)} grid"
                )
            for r in range(cell.row, cell.row + cell.row_span):
                for c in range(cell.column, cell.column + cell.column_span):
                    if (r, c) in taken:
                        raise GridOverlap(
                            f"cells {taken[(r, c)]} and {index} overlap at ({r}, {c})"
                        )
                    taken[(r, c)] = index
        object.__setattr__(self, "column_widths", widths)
        object.__setattr__(self, "row_heights", heights)
        object.__setattr__(self, "cells", cells)
        seen: set[int] = set()
        for panel in self.panels():
            if id(panel) in seen:
                raise InvalidData("the same panel cannot fill two cells")
            seen.add(id(panel))

    def panels(self) -> Iterator[Panel]:
        """Yield every panel of the grid, nested grids included, in cell order."""
        for cell in self.cells:
            if isinstance(cell.content, Panel):
                yield cell.content
            else:
                yield from cell.content.panels()


def single_panel_grid() -> Grid:
    """Return a 1 × 1 grid holding one new empty panel (G3)."""
    return Grid((1.0,), (1.0,), (Cell(0, 0, content=Panel()),))


@dataclass(eq=False, kw_only=True)
class Canvas:
    """One figure: a size and a grid of panels."""

    name: str
    size_cm: tuple[float, float] = DEFAULT_CANVAS_SIZE_CM
    grid: Grid = field(default_factory=single_panel_grid)
    align_rows: bool = True
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        w, h = _positive_tuple(self.size_cm, "canvas size")
        self.size_cm = (w, h)


@dataclass(eq=False, kw_only=True)
class Project:
    """Everything the user is working on: a list of canvases."""

    canvases: list[Canvas] = field(default_factory=list)
    metadata: Mapping[str, str] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.metadata = MappingProxyType(dict(self.metadata))
