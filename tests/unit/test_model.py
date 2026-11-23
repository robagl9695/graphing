# SPDX-License-Identifier: GPL-3.0-or-later
"""Value objects and containers of the figure model: construction and invariants."""

from __future__ import annotations

import pytest
from model_helpers import GAUSS_03_EV, uv_abs, uv_sticks

from graphing.core.errors import (
    GridOverlap,
    InvalidData,
    InvalidUnit,
    MissingBroadening,
    NonPositiveValue,
)
from graphing.core.interval import Interval
from graphing.core.model import (
    PALETTE,
    Broadening,
    Canvas,
    Cell,
    Grid,
    Inset,
    Layer,
    LayerArrangement,
    LineShape,
    Panel,
    Style,
    ZoomInset,
)
from graphing.core.operations import new_project
from graphing.core.units import Quantity, Unit


class TestBroadening:
    def test_defaults(self) -> None:
        b = Broadening(line_shape=LineShape.GAUSSIAN, fwhm=10, fwhm_unit=Unit.CM1)
        assert (b.scale_factor, b.step, b.fwhm_lorentzian) == (1.0, None, None)

    def test_voigt_needs_lorentzian_width(self) -> None:
        with pytest.raises(InvalidData):
            Broadening(line_shape=LineShape.VOIGT, fwhm=10, fwhm_unit=Unit.CM1)
        b = Broadening(
            line_shape=LineShape.VOIGT, fwhm=10, fwhm_unit=Unit.CM1, fwhm_lorentzian=4
        )
        assert b.fwhm_lorentzian == 4.0

    def test_voigt_lorentzian_width_positive(self) -> None:
        with pytest.raises(NonPositiveValue):
            Broadening(
                line_shape=LineShape.VOIGT,
                fwhm=10,
                fwhm_unit=Unit.CM1,
                fwhm_lorentzian=0.0,
            )

    def test_lorentzian_width_only_for_voigt(self) -> None:
        with pytest.raises(InvalidData):
            Broadening(
                line_shape=LineShape.GAUSSIAN,
                fwhm=10,
                fwhm_unit=Unit.CM1,
                fwhm_lorentzian=4,
            )

    def test_fwhm_in_nm_is_refused(self) -> None:
        # Broadening is linear in energy (T3.2, Rob S016).
        with pytest.raises(InvalidUnit):
            Broadening(line_shape=LineShape.GAUSSIAN, fwhm=20, fwhm_unit=Unit.NM)

    @pytest.mark.parametrize(
        "kwargs", [{"fwhm": 0.0}, {"scale_factor": -1.0}, {"step": 0.0}]
    )
    def test_non_positive(self, kwargs: dict[str, float]) -> None:
        args = {"line_shape": LineShape.GAUSSIAN, "fwhm": 0.3, "fwhm_unit": Unit.EV}
        args.update(kwargs)
        with pytest.raises(NonPositiveValue):
            Broadening(**args)  # type: ignore[arg-type]

    def test_fwhm_unit_must_be_x_unit(self) -> None:
        with pytest.raises(InvalidUnit):
            Broadening(line_shape=LineShape.GAUSSIAN, fwhm=1, fwhm_unit=Unit.PERCENT)


class TestStyle:
    def test_default_colour_is_first_of_palette(self) -> None:
        assert Style().colour == PALETTE[0] == "#0A5199"

    def test_bad_colour(self) -> None:
        with pytest.raises(InvalidData):
            Style(colour="blue")

    def test_cannot_hide_both_curve_and_sticks(self) -> None:
        with pytest.raises(InvalidData):
            Style(show_curve=False, show_sticks=False)

    def test_line_width_positive(self) -> None:
        with pytest.raises(NonPositiveValue):
            Style(line_width=0)


class TestLayer:
    def test_sticks_need_broadening(self) -> None:
        with pytest.raises(MissingBroadening):
            Layer(source=uv_sticks())

    def test_curve_refuses_broadening(self) -> None:
        with pytest.raises(InvalidData):
            Layer(source=uv_abs(), broadening=GAUSS_03_EV)

    def test_ids_are_unique(self) -> None:
        assert Layer(source=uv_abs()).id != Layer(source=uv_abs()).id


def test_arrangement_gap_positive() -> None:
    with pytest.raises(NonPositiveValue):
        LayerArrangement(stacked=True, gap=0.0)


class TestGrid:
    def test_rob_layout(self) -> None:
        # Architecture §10.5: one tall panel on the left, two on the right.
        p1, p2, p3 = Panel(), Panel(), Panel()
        grid = Grid(
            (1, 1),
            (7, 13),
            (
                Cell(0, 0, row_span=2, content=p1),
                Cell(0, 1, content=p2),
                Cell(1, 1, content=p3),
            ),
        )
        assert list(grid.panels()) == [p1, p2, p3]

    def test_nested_grid(self) -> None:
        a, b = Panel(), Panel()
        inner = Grid((1,), (5, 15), (Cell(0, 0, content=a), Cell(1, 0, content=b)))
        outer = Grid(
            (1, 1), (1,), (Cell(0, 0, content=inner), Cell(0, 1, content=Panel()))
        )
        assert list(outer.panels())[:2] == [a, b]

    def test_overlap(self) -> None:
        with pytest.raises(GridOverlap):
            Grid(
                (1, 1),
                (1, 1),
                (Cell(0, 0, row_span=2, content=Panel()), Cell(1, 0, content=Panel())),
            )

    def test_outside(self) -> None:
        with pytest.raises(InvalidData):
            Grid((1,), (1,), (Cell(0, 0, column_span=2, content=Panel()),))

    def test_cell_needs_content(self) -> None:
        with pytest.raises(InvalidData):
            Cell(0, 0, content=None)  # type: ignore[arg-type]

    def test_same_panel_twice(self) -> None:
        p = Panel()
        with pytest.raises(InvalidData):
            Grid((1, 1), (1,), (Cell(0, 0, content=p), Cell(0, 1, content=p)))

    def test_ratios_positive(self) -> None:
        with pytest.raises(NonPositiveValue):
            Grid((0,), (1,), (Cell(0, 0, content=Panel()),))


def test_new_canvas_has_one_empty_panel() -> None:
    # G3 and P1.
    canvas = new_project().canvases[0]
    panels = list(canvas.grid.panels())
    assert len(panels) == 1
    assert panels[0].is_empty and panels[0].x_axis is None and panels[0].y_left is None


def test_canvas_size_positive() -> None:
    with pytest.raises(NonPositiveValue):
        Canvas(name="c", size_cm=(20, 0))


@pytest.mark.parametrize(
    "placement",
    [(0.5, 0.5, 0.6, 0.2), (-0.1, 0, 0.5, 0.5), (0, 0, 0, 0.5), (0, 0, 0.5)],
)
def test_bad_inset_placement(placement: tuple[float, ...]) -> None:
    region = Interval(450, 520, Quantity.WAVELENGTH, Unit.NM)
    with pytest.raises(InvalidData):
        Inset(placement=placement, kind=ZoomInset(region=region))  # type: ignore[arg-type]
