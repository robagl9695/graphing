# SPDX-License-Identifier: GPL-3.0-or-later
"""What a layer shows: the evaluation pipeline of architecture §8.

Read-only: nothing here changes the model. ``render/`` and peak picking call
:func:`layer_values`; the operations use the same functions to check a change
before committing it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from graphing.core.broadening import (
    broaden,
    broadened_lines,
    broadening_quantity,
    corrected_sticks,
    profile_peak,
)
from graphing.core.data import CurveData, StickData
from graphing.core.errors import (
    CannotNormalise,
    DivisionByZero,
    EmptyPanel,
    InvalidTransform,
    NonPositiveValue,
    UnknownItem,
)
from graphing.core.interval import Interval
from graphing.core.model.axes import LayerArrangement, Side, XAxis, YAxis
from graphing.core.model.broadening import Broadening
from graphing.core.model.panel import Layer, Panel
from graphing.core.region import crop, select_mask
from graphing.core.spectrum import Series, Spectrum, Technique
from graphing.core.transforms import (
    LinesToAbsorptivity,
    NormaliseAtX,
    NormaliseToMax,
    YQuantity,
    YTransform,
    apply_transforms,
)
from graphing.core.units import DEFAULT_UNIT, Quantity, Unit, convert_x

Array = NDArray[np.float64]
Sticks = tuple[Array, Array, NDArray[np.intp]]
CompatibilityKey = tuple[Technique | None, YQuantity]

# Transforms that divide the whole curve by one number taken from the curve. On the
# sticks of the same layer they divide by that same number, so sticks and curve stay
# in proportion (Rob S016). Every other transform acts on each stick height as on
# each curve value.
_SCALING_TRANSFORMS = (NormaliseToMax, NormaliseAtX)

# A stick height a transform cannot take (log10 of 0, 1/0) drops that stick only.
_POINTWISE_ERRORS = (NonPositiveValue, DivisionByZero, InvalidTransform)

# Default stack gap as a multiple of the tallest layer (architecture §7, confirmed
# by Rob in S006). For normalised layers the tallest is 1, so the gap is 1.1.
STACK_GAP_FACTOR: float = 1.1


@dataclass(frozen=True)
class LayerValues:
    """The arrays a layer shows, in the panel's x unit, after its arrangement.

    ``sticks`` holds the lines of a theoretical layer after steps 1–6 as
    ``(x, y, line_index)``; ``line_index`` points into the source lines (§8). The
    broadened curve is computed from these raw lines, never from summed sticks.
    """

    x: Array
    y: Array
    sticks: Sticks | None = None


def domain_of(series: Series) -> Technique | None:
    """Return the compatibility domain: the technique of a spectrum, else ``None``."""
    return series.technique if isinstance(series, Spectrum) else None


def transformed_quantity(series: Series, transforms: Sequence[YTransform]) -> YQuantity:
    """Return the y quantity of ``series`` after ``transforms``.

    For a stick spectrum this is the quantity of the sticks; the broadened curve keeps
    it (D-07, Rob S008).

    Raises
    ------
    InvalidTransform
        A transform does not fit the y quantity at its step.
    """
    quantity: YQuantity = series.data.y_quantity
    for transform in transforms:
        quantity = transform.result_quantity(quantity)
    return quantity


def effective_y_quantity(layer: Layer) -> YQuantity:
    """Return the layer's y quantity after its own transforms (architecture §3.6)."""
    return transformed_quantity(layer.source, layer.y_transforms)


def compatibility_key(layer: Layer) -> CompatibilityKey:
    """Return ``(domain, effective y quantity)``; equal keys may share a raw axis."""
    return domain_of(layer.source), effective_y_quantity(layer)


def unit_of(quantity: YQuantity) -> Unit:
    """Return the unit an axis shows for ``quantity``."""
    if isinstance(quantity, Quantity):
        return DEFAULT_UNIT[quantity]
    # log10 and inverse of a quantity are shown without a unit.
    return Unit.DIMENSIONLESS


def transformed_values(layer: Layer, x_axis: XAxis) -> tuple[Array, Array]:
    """Run steps 1–5 of the pipeline and return the curve ``(x, y)``.

    For a stick layer the curve is the broadened one (step 3).

    Raises
    ------
    EmptySelection
        The crop leaves too few points.
    InvalidData
        A stick layer has no line above zero.
    InvalidTransform, NonPositiveValue, DivisionByZero, CannotNormalise
        A y transform cannot be applied to these values.
    """
    x, y, _ = transformed_layer(layer, x_axis)
    return x, y


def transformed_layer(
    layer: Layer, x_axis: XAxis
) -> tuple[Array, Array, Sticks | None]:
    """Run steps 1–5 of the pipeline: read, broaden, crop, convert x, y transforms.

    Returns
    -------
    x, y, sticks
        The curve, and for a stick layer its lines as ``(x, y, line_index)`` after
        the same steps (``None`` for a curve layer). The curve is always broadened
        from the raw lines, never from what the sticks show.

    Raises
    ------
    Same as :func:`transformed_values`.
    """
    data = layer.source.data
    if not isinstance(data, StickData):
        if layer.crop is not None:
            data = crop(data, layer.crop)
        x, y = convert_x(data.x, data.y, data.x_quantity, x_axis.quantity)
        y = _transform_curve(x, y, x_axis.quantity, data, layer.y_transforms)
        return x, y, None
    assert layer.broadening is not None  # Layer invariant
    curve = broaden(data, layer.broadening)  # corrects the positions itself (T3.3)
    if layer.crop is not None:
        curve = crop(curve, layer.crop)
    x, y = convert_x(curve.x, curve.y, curve.x_quantity, x_axis.quantity)
    # The drawn sticks use the same corrected positions as the curve.
    corrected = corrected_sticks(data, layer.broadening)
    sticks = _sticks_in(corrected, layer.crop, x_axis.quantity)
    return _transform_with_sticks(
        x,
        y,
        sticks,
        x_axis.quantity,
        data.y_quantity,
        layer.y_transforms,
        layer.broadening,
    )


def _transform_curve(
    x: Array,
    y: Array,
    x_quantity: Quantity,
    data: CurveData,
    transforms: Sequence[YTransform],
) -> Array:
    """Apply ``transforms`` to a curve layer.

    A conversion of line intensities to ε reads the y as a density per unit of the
    x the data were stored in, not of the view (T3.4).
    """
    if not any(isinstance(t, LinesToAbsorptivity) for t in transforms):
        result, _ = apply_transforms(x, y, x_quantity, data.y_quantity, transforms)
        return result
    quantity: YQuantity = data.y_quantity
    for transform in transforms:
        next_quantity = transform.result_quantity(quantity)
        own = data.x_quantity if isinstance(transform, LinesToAbsorptivity) else None
        y = transform.apply(x, y, own or x_quantity)
        quantity = next_quantity
    return y


def _sticks_in(
    data: StickData, interval: Interval | None, quantity: Quantity
) -> Sticks:
    """Return the drawn lines inside ``interval``, in ``quantity``, x ascending."""
    keep = broadened_lines(data)
    if interval is not None:
        keep &= select_mask(data, interval)
    index = np.flatnonzero(keep)
    x, order = convert_x(
        data.x[index], index.astype(np.float64), data.x_quantity, quantity
    )
    line_index = order.astype(np.intp)
    return x, np.array(data.y[line_index], dtype=np.float64), line_index


def _transform_with_sticks(
    x: Array,
    y: Array,
    sticks: Sticks,
    x_quantity: Quantity,
    y_quantity: YQuantity,
    transforms: Sequence[YTransform],
    broadening: Broadening,
) -> tuple[Array, Array, Sticks]:
    """Apply ``transforms`` to the curve and, consistently, to its sticks.

    The curve y is a density per unit of the broadening x, whatever the view. A
    conversion to ε takes each stick to the maximum of its own band (D-20261122-08).
    """
    quantity = y_quantity
    for transform in transforms:
        next_quantity = transform.result_quantity(quantity)
        if isinstance(transform, LinesToAbsorptivity):
            own = broadening_quantity(broadening)
            new_y = transform.apply(x, y, own)
            peak = transform.factor(own) * profile_peak(broadening)
            sticks = (sticks[0], sticks[1] * peak, sticks[2])
            y, quantity = new_y, next_quantity
            continue
        new_y = transform.apply(x, y, x_quantity)
        if isinstance(transform, _SCALING_TRANSFORMS):
            # The divisor the transform used, recovered where the curve is largest
            # (non-zero there, or the transform would have raised).
            i = int(np.argmax(np.abs(new_y)))
            sticks = (sticks[0], sticks[1] / (y[i] / new_y[i]), sticks[2])
        else:
            sticks = _pointwise(transform, sticks, x_quantity)
        y, quantity = new_y, next_quantity
    return x, y, sticks


def _pointwise(transform: YTransform, sticks: Sticks, x_quantity: Quantity) -> Sticks:
    """Apply ``transform`` to each stick height; drop the sticks it cannot take."""
    xs, ys, index = sticks
    try:
        return xs, transform.apply(xs, ys, x_quantity), index
    except _POINTWISE_ERRORS:
        pass
    kept: list[int] = []
    values: list[float] = []
    for i in range(xs.size):
        try:
            value = transform.apply(xs[i : i + 1], ys[i : i + 1], x_quantity)
        except _POINTWISE_ERRORS:
            continue
        kept.append(i)
        values.append(float(value[0]))
    keep = np.array(kept, dtype=np.intp)
    return xs[keep], np.array(values, dtype=np.float64), index[keep]


def arrange(
    values: Sequence[Array],
    already_normalised: Sequence[bool],
    gaps: Sequence[float | None],
    arrangement: LayerArrangement,
) -> list[Array]:
    """Apply step 6 (architecture §7) to the y arrays of one side, in drawing order.

    Parameters
    ----------
    values
        y of each layer after step 5.
    already_normalised
        Whether each layer's own transforms already normalise it; it is not
        normalised twice.
    gaps
        Each layer's own ``stack_gap`` (``None`` = the side's gap).
    arrangement
        The side's arrangement.

    Raises
    ------
    CannotNormalise
        A layer to normalise has a maximum that is not above zero.
    """
    coefficients = arrangement_coefficients(
        values, already_normalised, gaps, arrangement
    )
    return [_place(y, c) for y, c in zip(values, coefficients, strict=True)]


def _place(y: Array, coefficients: tuple[float, float]) -> Array:
    divisor, offset = coefficients
    placed = y / divisor if divisor != 1.0 else y
    return placed + offset if offset != 0.0 else placed


def arrangement_coefficients(
    values: Sequence[Array],
    already_normalised: Sequence[bool],
    gaps: Sequence[float | None],
    arrangement: LayerArrangement,
) -> list[tuple[float, float]]:
    """Return ``(divisor, offset)`` per layer for step 6: shown = y / divisor + offset.

    The same numbers apply to a layer's sticks, so they stay with its curve. Arguments
    and errors are those of :func:`arrange`.
    """
    divisors: list[float] = []
    for y, done in zip(values, already_normalised, strict=True):
        divisor = 1.0
        if arrangement.normalised and not done:
            divisor = float(y.max())
            if not divisor > 0:
                raise CannotNormalise(
                    f"a layer's maximum is {divisor:g}; "
                    "it must be above zero to normalise"
                )
        divisors.append(divisor)
    if not arrangement.stacked or not values:
        return [(d, 0.0) for d in divisors]
    side_gap = arrangement.gap
    if side_gap is None:
        tallest = (
            1.0
            if arrangement.normalised
            else max(
                float(_place(y, (d, 0.0)).max())
                for y, d in zip(values, divisors, strict=True)
            )
        )
        side_gap = STACK_GAP_FACTOR * tallest
    baseline = 0.0
    result: list[tuple[float, float]] = []
    for index, (divisor, own_gap) in enumerate(zip(divisors, gaps, strict=True)):
        if index > 0:
            baseline += side_gap if own_gap is None else own_gap
        result.append((divisor, baseline))
    return result


def side_values(
    layers: Sequence[Layer], y_axis: YAxis, x_axis: XAxis
) -> list[LayerValues]:
    """Evaluate every layer of one y side, in drawing order (steps 1–6)."""
    raw = [transformed_layer(layer, x_axis) for layer in layers]
    coefficients = arrangement_coefficients(
        [y for _, y, _ in raw],
        [effective_y_quantity(L) is Quantity.NORMALISED_INTENSITY for L in layers],
        [layer.stack_gap for layer in layers],
        y_axis.arrangement,
    )
    out: list[LayerValues] = []
    for (x, y, sticks), c in zip(raw, coefficients, strict=True):
        placed = None
        if sticks is not None:
            placed = (sticks[0], _place(sticks[1], c), sticks[2])
        out.append(LayerValues(x, _place(y, c), placed))
    return out


def layers_on(panel: Panel, side: Side) -> list[Layer]:
    """Return the layers drawn against ``side``, in drawing order."""
    return [layer for layer in panel.layers if layer.y_axis_side is side]


def layer_values(layer: Layer, panel: Panel) -> LayerValues:
    """Return what ``layer`` shows on ``panel``.

    Raises
    ------
    UnknownItem
        The layer is not on the panel.
    """
    if layer not in panel.layers:
        raise UnknownItem("the layer is not on this panel")
    y_axis = panel.y_axis(layer.y_axis_side)
    assert panel.x_axis is not None and y_axis is not None  # P1, P4
    side = layers_on(panel, layer.y_axis_side)
    return side_values(side, y_axis, panel.x_axis)[side.index(layer)]


def y_axis_state(panel: Panel, side: Side) -> YAxis | None:
    """Return the y axis of ``side`` (quantity, unit, domain, arrangement).

    Raises
    ------
    EmptyPanel
        The panel has no layers.
    """
    if panel.is_empty:
        raise EmptyPanel("the panel has no layers, so it has no y axis yet")
    return panel.y_axis(side)
