# SPDX-License-Identifier: GPL-3.0-or-later
"""Y values of the layer arrangements (T1.6 AC3, architecture §7 and §10.3)."""

from __future__ import annotations

import numpy as np
import pytest
from model_helpers import CM1, GAUSS_03_EV, NM, ir_abs, uv_abs, uv_sticks

from graphing.core.errors import CannotNormalise
from graphing.core.evaluate import layer_values, transformed_values
from graphing.core.interval import Interval
from graphing.core.model import (
    NORMALISED_OVERLAP,
    Layer,
    LayerArrangement,
    Panel,
    Side,
    Style,
)
from graphing.core.operations import (
    Normalise,
    add_layer,
    add_y_transform,
    set_arrangement,
    set_crop,
    set_stack_gap,
    set_style,
    set_x_limits,
    set_x_quantity,
)
from graphing.core.transforms import (
    Inverse,
    Level,
    Log10,
    NormaliseAtX,
    NormaliseToMax,
)
from graphing.core.units import Quantity, Unit, convert_x

# Values are produced by one division and one addition per point.
ATOL = 1e-12


def four_ir(scales: tuple[float, ...] = (1.0, 2.0, 0.5, 4.0)) -> Panel:
    panel = Panel()
    for i, scale in enumerate(scales):
        add_layer(panel, ir_abs(f"ir{i}", scale=scale))
    return panel


def raw_y(panel: Panel) -> list[np.ndarray]:
    assert panel.x_axis is not None
    return [transformed_values(L, panel.x_axis)[1] for L in panel.layers]


def test_overlap_keeps_values() -> None:
    panel = four_ir()
    for layer, y in zip(panel.layers, raw_y(panel), strict=True):
        np.testing.assert_allclose(layer_values(layer, panel).y, y, atol=ATOL)


def test_normalised_overlap_max_is_one() -> None:
    panel = four_ir()
    set_arrangement(panel, Side.LEFT, NORMALISED_OVERLAP)
    for layer, y in zip(panel.layers, raw_y(panel), strict=True):
        values = layer_values(layer, panel)
        assert values.y.max() == pytest.approx(1.0, abs=ATOL)
        np.testing.assert_allclose(values.y, y / y.max(), atol=ATOL)


def baselines(panel: Panel) -> list[float]:
    # Each layer is its normalised self plus a constant: recover the constant.
    out = []
    for layer, y in zip(panel.layers, raw_y(panel), strict=True):
        shift = layer_values(layer, panel).y - y / y.max()
        assert np.ptp(shift) < ATOL
        out.append(float(shift[0]))
    return out


def test_stacked_normalised_baselines() -> None:
    # Architecture §10.3.
    panel = four_ir()
    set_arrangement(
        panel, Side.LEFT, LayerArrangement(normalised=True, stacked=True, gap=None)
    )
    assert baselines(panel) == pytest.approx([0.0, 1.1, 2.2, 3.3], abs=ATOL)
    set_stack_gap(panel.layers[2], 1.5)
    assert baselines(panel) == pytest.approx([0.0, 1.1, 2.6, 3.7], abs=ATOL)


def test_stacked_side_gap() -> None:
    panel = four_ir()
    set_arrangement(
        panel, Side.LEFT, LayerArrangement(normalised=True, stacked=True, gap=2.0)
    )
    assert baselines(panel) == pytest.approx([0.0, 2.0, 4.0, 6.0], abs=ATOL)


def test_stacked_raw_default_gap() -> None:
    # Gap = 1.1 × the tallest layer (max 4.0 here, within the sampled grid).
    panel = four_ir()
    set_arrangement(panel, Side.LEFT, LayerArrangement(stacked=True))
    tallest = max(float(y.max()) for y in raw_y(panel))
    for i, (layer, y) in enumerate(zip(panel.layers, raw_y(panel), strict=True)):
        shift = layer_values(layer, panel).y - y
        np.testing.assert_allclose(shift, i * 1.1 * tallest, atol=ATOL)


def test_layer_already_normalised_is_not_normalised_twice() -> None:
    panel = Panel()
    add_layer(panel, uv_abs("a"))
    b = add_layer(panel, ir_abs("b"), resolution=Normalise())
    # Normalise b at a point where it is half of its maximum: its max becomes 2.
    x_half = 1700.0 + 50.0 * np.sqrt(np.log(2.0))
    add_y_transform(panel, b, NormaliseAtX(x_half, CM1, Unit.CM1))
    assert layer_values(b, panel).y.max() == pytest.approx(2.0, rel=1e-2)


def test_normalisation_uses_cropped_data() -> None:
    panel = Panel()
    layer = add_layer(panel, uv_abs())
    set_crop(panel, layer, Interval(500, 600, NM, Unit.NM))
    set_arrangement(panel, Side.LEFT, NORMALISED_OVERLAP)
    values = layer_values(layer, panel)
    assert values.x[0] == pytest.approx(500.0) and values.y.max() == pytest.approx(1.0)
    assert values.y[0] == pytest.approx(1.0)  # 500 nm is the cropped maximum


def test_cannot_normalise_non_positive() -> None:
    panel = Panel()
    layer = add_layer(panel, uv_abs())
    add_y_transform(panel, layer, Level(5.0))  # every value now below zero
    with pytest.raises(CannotNormalise):
        set_arrangement(panel, Side.LEFT, NORMALISED_OVERLAP)


# --- Stick layers (T3.2) ---------------------------------------------------------


def stick_panel() -> tuple[Panel, Layer]:
    panel = Panel()
    layer = add_layer(panel, uv_sticks(), broadening=GAUSS_03_EV)
    return panel, layer


def test_stick_layer_gives_curve_and_sticks() -> None:
    panel, layer = stick_panel()
    values = layer_values(layer, panel)
    assert values.sticks is not None
    xs, ys, index = values.sticks
    np.testing.assert_array_equal(xs, [2.5, 3.1, 4.0])
    np.testing.assert_array_equal(ys, [0.1, 0.4, 0.2])
    np.testing.assert_array_equal(index, [0, 1, 2])
    assert values.x[0] < 2.5 < 4.0 < values.x[-1]


@pytest.mark.parametrize(("quantity", "unit"), [(NM, Unit.NM), (CM1, Unit.CM1)])
def test_ac2_curve_does_not_depend_on_display_unit(
    quantity: Quantity, unit: Unit
) -> None:
    panel, layer = stick_panel()
    in_ev = layer_values(layer, panel)
    set_x_quantity(panel, quantity, unit)
    shown = layer_values(layer, panel)
    back_x, back_y = convert_x(shown.x, shown.y, quantity, Quantity.ENERGY)
    np.testing.assert_allclose(back_x, in_ev.x, rtol=1e-12)
    np.testing.assert_array_equal(back_y, in_ev.y)
    assert shown.sticks is not None and in_ev.sticks is not None
    sx, sy = convert_x(shown.sticks[0], shown.sticks[1], quantity, Quantity.ENERGY)
    np.testing.assert_allclose(sx, in_ev.sticks[0], rtol=1e-12)
    np.testing.assert_array_equal(sy, in_ev.sticks[1])


def test_ac3_curve_does_not_depend_on_the_view() -> None:
    panel, layer = stick_panel()
    before = layer_values(layer, panel).y
    set_style(layer, Style(sum_sticks=False))
    set_x_limits(panel, (2.9, 3.2))
    np.testing.assert_array_equal(layer_values(layer, panel).y, before)


def test_sticks_follow_the_curve_when_normalised() -> None:
    panel, layer = stick_panel()
    raw = layer_values(layer, panel)
    set_arrangement(panel, Side.LEFT, NORMALISED_OVERLAP)
    shown = layer_values(layer, panel)
    assert shown.sticks is not None and raw.sticks is not None
    top = raw.y.max()
    np.testing.assert_allclose(shown.sticks[1], raw.sticks[1] / top, rtol=1e-12)


def test_sticks_follow_a_normalise_transform() -> None:
    panel, layer = stick_panel()
    raw = layer_values(layer, panel)
    add_y_transform(panel, layer, NormaliseToMax())
    shown = layer_values(layer, panel)
    assert shown.sticks is not None and raw.sticks is not None
    np.testing.assert_allclose(shown.sticks[1], raw.sticks[1] / raw.y.max(), rtol=1e-12)


def test_sticks_are_offset_with_their_layer_when_stacked() -> None:
    panel, _ = stick_panel()
    upper = add_layer(panel, uv_sticks("second"), broadening=GAUSS_03_EV)
    set_arrangement(panel, Side.LEFT, LayerArrangement(stacked=True, gap=5.0))
    shown = layer_values(upper, panel)
    assert shown.sticks is not None
    np.testing.assert_allclose(shown.sticks[1], [5.1, 5.4, 5.2], rtol=1e-12)


def test_level_and_log_act_on_each_stick() -> None:
    panel, layer = stick_panel()
    add_y_transform(panel, layer, Log10())
    shown = layer_values(layer, panel)
    assert shown.sticks is not None
    np.testing.assert_allclose(shown.sticks[1], np.log10([0.1, 0.4, 0.2]))


def test_a_stick_a_transform_cannot_take_is_dropped() -> None:
    # Levelling by 0.1 brings the 0.1 stick to exactly 0, which 1/y cannot take; the
    # curve has no exact zero and is still shown, as are the other two sticks.
    panel, layer = stick_panel()
    add_y_transform(panel, layer, Level(0.1))
    add_y_transform(panel, layer, Inverse())
    shown = layer_values(layer, panel)
    assert shown.sticks is not None
    np.testing.assert_array_equal(shown.sticks[2], [1, 2])
    np.testing.assert_allclose(shown.sticks[1], [1 / 0.3, 1 / 0.1], rtol=1e-12)


def test_crop_limits_the_sticks() -> None:
    panel, layer = stick_panel()
    set_crop(panel, layer, Interval(3.0, 4.5, Quantity.ENERGY, Unit.EV))
    shown = layer_values(layer, panel)
    assert shown.sticks is not None
    np.testing.assert_array_equal(shown.sticks[2], [1, 2])
    assert shown.x[0] >= 3.0 * (1 - 1e-9)


def test_t33_sticks_follow_the_corrected_positions() -> None:
    from graphing.core.model import Broadening, LineShape

    b = Broadening(
        line_shape=LineShape.GAUSSIAN,
        fwhm=0.3,
        fwhm_unit=Unit.EV,
        scale_factor=1.1,
        shift=-0.2,
    )
    panel = Panel()
    layer = add_layer(panel, uv_sticks(), broadening=b)
    values = layer_values(layer, panel)
    assert values.sticks is not None
    np.testing.assert_allclose(values.sticks[0], [2.55, 3.21, 4.2], rtol=1e-12)
    peak = values.x[np.argmax(values.y)]
    assert peak == pytest.approx(3.21, abs=0.05)  # the tallest line, corrected
