# SPDX-License-Identifier: GPL-3.0-or-later
"""Operations on the model (T1.6 AC1, AC2, AC4, AC5 and the y rules of §6)."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from model_helpers import CM1, GAUSS_03_EV, NM, curve, ir_abs, uv_abs, uv_sticks

from graphing.core import constants
from graphing.core.errors import (
    EmptySelection,
    IncompatibleXQuantity,
    IncompatibleYQuantity,
    InvalidTransform,
    InvalidUnit,
    MissingBroadening,
    NestedInset,
    RegionInBreak,
    StackedWithDualAxis,
    UnknownItem,
    YChoiceRequired,
)
from graphing.core.evaluate import layer_values
from graphing.core.interval import Interval
from graphing.core.model import (
    NORMALISED_OVERLAP,
    OVERLAP,
    STACKED,
    LayerArrangement,
    Panel,
    Side,
    Style,
    ZoomInset,
)
from graphing.core.operations import (
    DualAxis,
    NeedsYChoice,
    Normalise,
    Ok,
    YChoice,
    add_free_inset,
    add_layer,
    add_y_transform,
    add_zoom_inset,
    assign_y_axis_sides,
    check_add_layer,
    move_layer,
    paste_layer,
    remove_inset,
    remove_layer,
    set_arrangement,
    set_breaks,
    set_crop,
    set_style,
    set_x_inverted,
    set_x_limits,
    set_x_quantity,
)
from graphing.core.spectrum import Technique
from graphing.core.transforms import Level, TransmittanceToAbsorbance, YQuantity
from graphing.core.units import Quantity, Unit

# Conversions between nm and cm⁻¹ are exact up to rounding; relative tolerance.
RTOL = 1e-12


def snapshot(panel: Panel) -> tuple[object, ...]:
    """Everything an operation could change, to check that failures change nothing."""
    return (
        panel.x_axis,
        panel.y_left,
        panel.y_right,
        [(L.id, L.y_axis_side, L.y_transforms, L.crop, L.style) for L in panel.layers],
        [(i.id, i.placement, i.kind) for i in panel.insets],
    )


def yq(panel: Panel, side: Side) -> YQuantity:
    """Quantity of one y axis, read afresh (operations replace the axis object)."""
    axis = panel.y_axis(side)
    assert axis is not None
    return axis.quantity


# ---------------------------------------------------------------- AC1 inheritance


class TestAC1Inheritance:
    def test_first_layer_sets_axes(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        assert panel.x_axis is not None and panel.y_left is not None
        assert (panel.x_axis.quantity, panel.x_axis.unit) == (NM, Unit.NM)
        assert not panel.x_axis.inverted
        assert yq(panel, Side.LEFT) is Quantity.ABSORBANCE
        assert panel.y_left.domain is Technique.UV_VIS
        assert panel.y_left.arrangement == OVERLAP
        assert panel.y_right is None

    def test_first_ir_layer_inverts_x(self) -> None:
        panel = Panel()
        add_layer(panel, ir_abs())
        assert panel.x_axis is not None
        assert panel.x_axis.quantity is CM1 and panel.x_axis.inverted

    def test_later_layer_is_converted(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        # Same technique and quantity, but given in cm⁻¹.
        x_cm1 = np.linspace(17000.0, 33000.0, 50)
        layer = add_layer(
            panel, curve(x_cm1, np.ones(50), x_quantity=CM1, name="in cm-1")
        )
        values = layer_values(layer, panel)
        expected = np.sort(constants.NM_TO_CM1 / x_cm1)
        np.testing.assert_allclose(values.x, expected, rtol=RTOL)
        assert layer.y_axis_side is Side.LEFT

    def test_later_layer_does_not_reset_display_defaults(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        add_layer(panel, ir_abs(), resolution=Normalise())
        assert panel.x_axis is not None and not panel.x_axis.inverted

    def test_removing_last_layer_empties_panel(self) -> None:
        panel = Panel()
        layer = add_layer(panel, uv_abs())
        remove_layer(panel, layer)
        assert panel.is_empty and panel.x_axis is None and panel.y_left is None


# ------------------------------------------------------- AC2 changing x quantity


class TestAC2ChangeX:
    def test_every_layer_follows(self) -> None:
        panel = Panel()
        a = add_layer(panel, uv_abs("a"))
        b = add_layer(panel, uv_abs("b", scale=0.5))
        set_x_quantity(panel, CM1, Unit.CM1)
        for layer in (a, b):
            values = layer_values(layer, panel)
            raw = layer.source.data.x
            np.testing.assert_allclose(
                values.x, np.sort(constants.NM_TO_CM1 / raw), rtol=RTOL
            )

    def test_limits_regions_and_breaks_follow(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        set_x_limits(panel, (400.0, 500.0))
        set_breaks(panel, (Interval(350, 360, NM, Unit.NM),))
        inset = add_zoom_inset(
            panel, Interval(450, 520, NM, Unit.NM), (0.55, 0.5, 0.4, 0.4)
        )
        set_x_quantity(panel, CM1, Unit.CM1)
        assert panel.x_axis is not None
        assert panel.x_axis.limits == pytest.approx((20000.0, 25000.0), rel=RTOL)
        brk = panel.x_axis.breaks[0]
        assert (brk.low, brk.high) == pytest.approx((1e7 / 360, 1e7 / 350), rel=RTOL)
        assert isinstance(inset.kind, ZoomInset)
        region = inset.kind.region
        # Architecture §10.6: 450–520 nm becomes 19 231–22 222 cm⁻¹.
        assert region.unit is Unit.CM1
        assert (round(region.low), round(region.high)) == (19231, 22222)

    def test_user_inversion_is_kept(self) -> None:
        panel = Panel()
        add_layer(panel, ir_abs())
        set_x_inverted(panel, False)
        set_x_quantity(panel, NM, Unit.NM)
        assert panel.x_axis is not None and not panel.x_axis.inverted

    def test_bad_target(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        before = snapshot(panel)
        with pytest.raises(IncompatibleXQuantity):
            set_x_quantity(panel, Quantity.ABSORBANCE, Unit.DIMENSIONLESS)
        with pytest.raises(InvalidUnit):
            set_x_quantity(panel, CM1, Unit.NM)
        assert snapshot(panel) == before


# ---------------------------------------------------- y compatibility (§6, §10)


class TestYChoice:
    def test_compatible_goes_left(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs("a"))
        assert check_add_layer(panel, uv_abs("b")) == Ok(Side.LEFT)

    def test_different_technique_needs_choice(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        result = check_add_layer(panel, ir_abs())
        assert result == NeedsYChoice((YChoice.NORMALISE, YChoice.DUAL_AXIS))

    def test_transformed_layer_becomes_compatible(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        x = np.linspace(300, 600, 10)
        t = curve(x, np.full(10, 50.0), y_quantity=Quantity.TRANSMITTANCE)
        assert isinstance(check_add_layer(panel, t), NeedsYChoice)
        assert check_add_layer(panel, t, [TransmittanceToAbsorbance()]) == Ok(Side.LEFT)

    def test_normalised_overlap_example(self) -> None:
        # Architecture §10.2.
        panel = Panel()
        add_layer(panel, uv_abs())
        uv_th = uv_sticks()
        assert isinstance(check_add_layer(panel, uv_th), NeedsYChoice)
        add_layer(panel, uv_th, resolution=Normalise(), broadening=GAUSS_03_EV)
        assert panel.y_left is not None and panel.y_right is None
        assert yq(panel, Side.LEFT) is Quantity.NORMALISED_INTENSITY
        assert panel.y_left.arrangement == NORMALISED_OVERLAP

    def test_double_axis_example(self) -> None:
        # Architecture §10.4.
        panel = Panel()
        uv = add_layer(panel, uv_abs())
        ir = add_layer(panel, ir_abs(), resolution=DualAxis(Side.RIGHT))
        assert panel.y_left is not None and panel.y_right is not None
        assert (panel.y_left.quantity, panel.y_left.domain) == (
            Quantity.ABSORBANCE,
            Technique.UV_VIS,
        )
        assert (panel.y_right.quantity, panel.y_right.domain) == (
            Quantity.ABSORBANCE,
            Technique.IR,
        )
        th = add_layer(
            panel, uv_sticks(), resolution=DualAxis(Side.LEFT), broadening=GAUSS_03_EV
        )
        assert yq(panel, Side.LEFT) is Quantity.NORMALISED_INTENSITY
        assert yq(panel, Side.RIGHT) is Quantity.ABSORBANCE
        assert [L.y_axis_side for L in (uv, ir, th)] == [
            Side.LEFT,
            Side.RIGHT,
            Side.LEFT,
        ]

    def test_both_sides_normalised_collapse(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        ir = add_layer(panel, ir_abs(), resolution=DualAxis(Side.RIGHT))
        th = add_layer(
            panel, uv_sticks(), resolution=DualAxis(Side.RIGHT), broadening=GAUSS_03_EV
        )
        # Right would hold IR + theory (normalised); left UV only stays raw.
        assert panel.y_right is not None
        assert yq(panel, Side.RIGHT) is Quantity.NORMALISED_INTENSITY
        assign_y_axis_sides(panel, {th.id: Side.LEFT})
        # Now left = UV + theory (normalised), right = IR (raw): still two axes.
        assert yq(panel, Side.RIGHT) is Quantity.ABSORBANCE
        set_arrangement(panel, Side.RIGHT, NORMALISED_OVERLAP)
        # P5: both normalised collapses into one axis.
        assert panel.y_right is None
        assert all(L.y_axis_side is Side.LEFT for L in panel.layers)
        assert ir.y_axis_side is Side.LEFT

    def test_layer_matching_right_axis_goes_right(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        add_layer(panel, ir_abs(), resolution=DualAxis(Side.RIGHT))
        assert check_add_layer(panel, ir_abs("ir2")) == Ok(Side.RIGHT)

    def test_normalised_side_stays_normalised_after_removal(self) -> None:
        # Rob, S008 (point 3).
        panel = Panel()
        add_layer(panel, uv_abs())
        ir = add_layer(panel, ir_abs(), resolution=Normalise())
        remove_layer(panel, ir)
        assert panel.y_left is not None
        assert yq(panel, Side.LEFT) is Quantity.NORMALISED_INTENSITY

    def test_right_axis_disappears_with_its_last_layer(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        ir = add_layer(panel, ir_abs(), resolution=DualAxis(Side.RIGHT))
        remove_layer(panel, ir)
        assert panel.y_right is None

    def test_transform_changes_axis_quantity(self) -> None:
        # Architecture §10.7.
        panel = Panel()
        x = np.linspace(500, 4000, 20)
        layer = add_layer(
            panel,
            curve(
                x,
                np.full(20, 80.0),
                x_quantity=CM1,
                y_quantity=Quantity.TRANSMITTANCE,
                technique=Technique.IR,
            ),
        )
        assert panel.y_left is not None
        assert yq(panel, Side.LEFT) is Quantity.TRANSMITTANCE
        add_y_transform(panel, layer, TransmittanceToAbsorbance())
        assert yq(panel, Side.LEFT) is Quantity.ABSORBANCE


# ------------------------------------------------------------- AC4 pasted copy


class TestAC4Paste:
    def test_copy_is_independent(self) -> None:
        source_panel, target = Panel(), Panel()
        original = add_layer(source_panel, uv_abs())
        add_y_transform(source_panel, original, Level(0.1))
        copy = paste_layer(original, target)
        assert copy.id != original.id
        assert copy.source is original.source  # shared, immutable
        assert copy.y_transforms == original.y_transforms
        add_y_transform(target, copy, Level(0.2))
        set_crop(target, copy, Interval(400, 500, NM, Unit.NM))
        set_style(copy, Style(colour="#AA1E1E"))
        assert original.y_transforms == (Level(0.1),)
        assert original.crop is None
        assert original.style.colour == "#0A5199"

    def test_paste_into_same_panel(self) -> None:
        panel = Panel()
        original = add_layer(panel, uv_abs())
        copy = paste_layer(original, panel)
        assert panel.layers == [original, copy]
        move_layer(panel, copy, 0)
        assert panel.layers == [copy, original]

    def test_paste_follows_target_rules(self) -> None:
        source_panel, target = Panel(), Panel()
        layer = add_layer(source_panel, ir_abs())
        add_layer(target, uv_abs())
        with pytest.raises(YChoiceRequired):
            paste_layer(layer, target)
        paste_layer(layer, target, resolution=Normalise())
        assert len(target.layers) == 2


# ---------------------------------------------------- AC5 forbidden combinations


class TestAC5Forbidden:
    def test_stacked_then_dual_axis(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        set_arrangement(panel, Side.LEFT, STACKED)
        assert check_add_layer(panel, ir_abs()) == NeedsYChoice((YChoice.NORMALISE,))
        before = snapshot(panel)
        with pytest.raises(StackedWithDualAxis):
            add_layer(panel, ir_abs(), resolution=DualAxis(Side.RIGHT))
        assert snapshot(panel) == before

    def test_dual_axis_then_stacked(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        add_layer(panel, ir_abs(), resolution=DualAxis(Side.RIGHT))
        before = snapshot(panel)
        for side in Side:
            with pytest.raises(StackedWithDualAxis):
                set_arrangement(panel, side, STACKED)
        assert snapshot(panel) == before

    def test_inset_in_free_inset(self) -> None:
        host, inner = Panel(), Panel()
        add_layer(host, uv_abs())
        add_layer(inner, ir_abs())
        inset = add_free_inset(host, inner, (0.05, 0.55, 0.35, 0.4))
        with pytest.raises(NestedInset):
            add_free_inset(inner, Panel(), (0, 0, 0.5, 0.5))
        with pytest.raises(NestedInset):
            add_zoom_inset(inner, Interval(1000, 2000, CM1, Unit.CM1), (0, 0, 0.5, 0.5))
        remove_inset(host, inset)
        assert not inner.is_inset

    def test_panel_with_insets_cannot_become_inset(self) -> None:
        host, inner = Panel(), Panel()
        add_layer(inner, uv_abs())
        add_zoom_inset(inner, Interval(450, 500, NM, Unit.NM), (0, 0, 0.5, 0.5))
        with pytest.raises(NestedInset):
            add_free_inset(host, inner, (0, 0, 0.5, 0.5))

    def test_x_not_convertible(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        with pytest.raises(IncompatibleXQuantity):
            set_x_quantity(panel, Quantity.INTENSITY, Unit.ARBITRARY)

    def test_sticks_without_broadening(self) -> None:
        panel = Panel()
        with pytest.raises(MissingBroadening):
            add_layer(panel, uv_sticks())
        assert panel.is_empty

    def test_incompatible_y_without_choice(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        before = snapshot(panel)
        with pytest.raises(YChoiceRequired):
            add_layer(panel, ir_abs())
        assert snapshot(panel) == before

    def test_unnormalising_mixed_side(self) -> None:
        panel = Panel()
        add_layer(panel, uv_abs())
        add_layer(panel, ir_abs(), resolution=Normalise())
        before = snapshot(panel)
        with pytest.raises(IncompatibleYQuantity):
            set_arrangement(panel, Side.LEFT, OVERLAP)
        assert snapshot(panel) == before

    def test_zoom_region_inside_break(self) -> None:
        panel = Panel()
        add_layer(panel, ir_abs())
        set_breaks(panel, (Interval(1800, 2500, CM1, Unit.CM1),))
        with pytest.raises(RegionInBreak):
            add_zoom_inset(panel, Interval(1900, 2000, CM1, Unit.CM1), (0, 0, 0.5, 0.5))


# --------------------------------------------- failures leave the model unchanged


class TestAtomic:
    def test_bad_transform(self) -> None:
        panel = Panel()
        layer = add_layer(panel, uv_abs())
        before = snapshot(panel)
        with pytest.raises(InvalidTransform):
            add_y_transform(panel, layer, TransmittanceToAbsorbance())
        assert snapshot(panel) == before

    def test_empty_crop(self) -> None:
        panel = Panel()
        layer = add_layer(panel, uv_abs())
        before = snapshot(panel)
        with pytest.raises(EmptySelection):
            set_crop(panel, layer, Interval(700, 800, NM, Unit.NM))
        assert snapshot(panel) == before

    def test_layer_of_another_panel(self) -> None:
        a, b = Panel(), Panel()
        layer = add_layer(a, uv_abs())
        with pytest.raises(UnknownItem):
            remove_layer(b, layer)

    def test_default_colours_cycle(self) -> None:
        panel = Panel()
        colours = [add_layer(panel, uv_abs(str(i))).style.colour for i in range(6)]
        assert colours == ["#0A5199", "#AA1E1E", "#8753C6", "#BF7B00", "#007D50"] + [
            "#0A5199"
        ]

    def test_arrangement_is_a_value(self) -> None:
        arrangement = LayerArrangement(normalised=True, stacked=True, gap=None)
        assert dataclasses.replace(arrangement, gap=2.0).gap == 2.0
