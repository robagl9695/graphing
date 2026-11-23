# SPDX-License-Identifier: GPL-3.0-or-later
"""Operations on the model, the only way the GUI changes it (architecture §12).

Each operation either succeeds or raises a named error and leaves the model exactly
as it was: the new state is computed and checked first, then committed.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum

from graphing.core.errors import (
    EmptyPanel,
    IncompatibleXQuantity,
    IncompatibleYQuantity,
    InvalidData,
    InvalidInterval,
    NestedInset,
    RegionInBreak,
    StackedWithDualAxis,
    UnknownItem,
    YChoiceRequired,
)
from graphing.core.evaluate import (
    CompatibilityKey,
    compatibility_key,
    domain_of,
    side_values,
    transformed_quantity,
    unit_of,
)
from graphing.core.interval import Interval
from graphing.core.model.axes import (
    OVERLAP,
    LayerArrangement,
    Scale,
    Side,
    XAxis,
    YAxis,
    check_gap,
    check_x_unit,
)
from graphing.core.model.broadening import Broadening
from graphing.core.model.canvas import Canvas, Grid, Project
from graphing.core.model.panel import (
    FreeInset,
    Inset,
    Layer,
    Panel,
    Placement,
    ZoomInset,
    check_broadening,
    check_placement,
    new_id,
)
from graphing.core.model.style import Style, default_style
from graphing.core.region import check_view_limits, crop
from graphing.core.spectrum import Series, Technique
from graphing.core.transforms import YQuantity, YTransform
from graphing.core.units import X_QUANTITIES, Quantity, Unit, convert_x

# --------------------------------------------------------------------------------
# Results of check_add_layer and the user's resolutions (architecture §6)
# --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Ok:
    """The layer can be added without asking; it goes to ``side``."""

    side: Side


class YChoice(Enum):
    """The options the GUI offers when a layer's y does not fit (§6)."""

    NORMALISE = "normalise"
    DUAL_AXIS = "double y axis"


@dataclass(frozen=True)
class NeedsYChoice:
    """The layer's y does not fit; the user must pick one of ``options``."""

    options: tuple[YChoice, ...]


@dataclass(frozen=True)
class Normalise:
    """Resolution (a): one normalised y axis holding every layer."""


@dataclass(frozen=True)
class DualAxis:
    """Resolution (b): a y side for the new layer and, optionally, for others.

    ``sides`` maps layer ids to their side; layers not listed keep theirs.
    """

    new_side: Side
    sides: Mapping[str, Side] = field(default_factory=dict)


Resolution = Normalise | DualAxis

# --------------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------------


def _require_layer(panel: Panel, layer: Layer) -> None:
    if not any(item is layer for item in panel.layers):
        raise UnknownItem(f"layer {layer.source.name!r} is not on this panel")


def _require_x_axis(panel: Panel) -> XAxis:
    if panel.x_axis is None:
        raise EmptyPanel("the panel has no layers yet; add one first")
    return panel.x_axis


def _require_y_axis(panel: Panel, side: Side) -> YAxis:
    _require_x_axis(panel)
    axis = panel.y_axis(side)
    if axis is None:
        raise UnknownItem(f"the panel has no {side.value} y axis")
    return axis


def _convert_limits(
    limits: tuple[float, float] | None, source: Quantity, target: Quantity
) -> tuple[float, float] | None:
    # View limits are display only; ends that cannot be converted (zero or below)
    # fall back to automatic limits instead of blocking the unit change.
    if limits is None or source is target:
        return limits
    low, high = limits
    if not (low > 0 and high > 0):
        return None
    ends, _ = convert_x([low, high], [0.0, 0.0], source, target)
    return float(ends[0]), float(ends[1])


def _side_axis(
    layers: Sequence[Layer], template: YAxis | None, arrangement: LayerArrangement
) -> YAxis:
    """Build the y axis of one side from its layers, keeping the user's options."""
    keys = {compatibility_key(layer) for layer in layers}
    domains = {domain for domain, _ in keys}
    domain = next(iter(domains)) if len(domains) == 1 else None
    y_quantity: YQuantity
    if arrangement.normalised:
        y_quantity = Quantity.NORMALISED_INTENSITY
    elif len(keys) == 1:
        y_quantity = next(iter(keys))[1]
    else:
        names = sorted(_key_text(k) for k in keys)
        raise IncompatibleYQuantity(
            "these layers cannot share a y axis without normalising it: "
            + "; ".join(names)
        )
    unit = unit_of(y_quantity)
    if template is None:
        return YAxis(
            quantity=y_quantity, unit=unit, domain=domain, arrangement=arrangement
        )
    # Limits chosen for another quantity would hide the data; they reset to automatic.
    limits = template.limits if template.quantity == y_quantity else None
    return dataclasses.replace(
        template,
        quantity=y_quantity,
        unit=unit,
        domain=domain,
        arrangement=arrangement,
        limits=limits,
    )


def _key_text(key: CompatibilityKey) -> str:
    domain, quantity = key
    where = domain.value if isinstance(domain, Technique) else "generic"
    what = quantity.value if isinstance(quantity, Quantity) else repr(quantity)
    return f"{where} {what}"


@dataclass
class _YPlan:
    """A candidate y state of a panel, checked before it is committed."""

    sides: dict[str, Side]
    left: LayerArrangement
    right: LayerArrangement
    left_template: YAxis | None
    right_template: YAxis | None


def _compute_y(
    layers: Sequence[Layer], plan: _YPlan
) -> tuple[YAxis | None, YAxis | None, dict[str, Side]]:
    """Apply invariants P3–P6 to a candidate and return the new y axes and sides."""
    sides = dict(plan.sides)
    left = [L for L in layers if sides[L.id] is Side.LEFT]
    right = [L for L in layers if sides[L.id] is Side.RIGHT]
    left_arr, right_arr = plan.left, plan.right
    left_tpl, right_tpl = plan.left_template, plan.right_template
    if right and not left:
        # A right axis alone is just a single axis: it becomes the left one.
        left, right = right, []
        left_arr, left_tpl = right_arr, right_tpl
        sides = dict.fromkeys(sides, Side.LEFT)
    if right:
        if left_arr.stacked or right_arr.stacked:
            raise StackedWithDualAxis(
                "a stacked y side cannot share the panel with a second y axis"
            )
        if left_arr.normalised and right_arr.normalised:
            # P5: two normalised sides show the same thing; collapse into one.
            left, right = list(layers), []
            sides = dict.fromkeys(sides, Side.LEFT)
    y_left = _side_axis(left, left_tpl, left_arr) if left else None
    y_right = _side_axis(right, right_tpl, right_arr) if right else None
    return y_left, y_right, sides


def _current_plan(panel: Panel) -> _YPlan:
    return _YPlan(
        sides={L.id: L.y_axis_side for L in panel.layers},
        left=panel.y_left.arrangement if panel.y_left else OVERLAP,
        right=panel.y_right.arrangement if panel.y_right else OVERLAP,
        left_template=panel.y_left,
        right_template=panel.y_right,
    )


def _validate_values(
    layers: Sequence[Layer],
    sides: Mapping[str, Side],
    x_axis: XAxis,
    y_left: YAxis | None,
    y_right: YAxis | None,
) -> None:
    # Layers are evaluated now so a bad transform or crop fails before the commit.
    for side, axis in ((Side.LEFT, y_left), (Side.RIGHT, y_right)):
        if axis is None:
            continue
        side_values([L for L in layers if sides[L.id] is side], axis, x_axis)


def _commit(
    panel: Panel,
    layers: list[Layer],
    plan: _YPlan,
    x_axis: XAxis | None = None,
    zoom_kinds: Sequence[tuple[Inset, ZoomInset]] = (),
) -> None:
    """Check a candidate panel state and, if it holds, write it into ``panel``."""
    new_x = x_axis if x_axis is not None else panel.x_axis
    y_left: YAxis | None = None
    y_right: YAxis | None = None
    sides: dict[str, Side] = {}
    if not layers:
        new_x = None
    else:
        y_left, y_right, sides = _compute_y(layers, plan)
        assert new_x is not None
        _validate_values(layers, sides, new_x, y_left, y_right)
    for layer in layers:
        layer.y_axis_side = sides[layer.id]
    panel.layers = list(layers)
    panel.x_axis = new_x
    panel.y_left = y_left
    panel.y_right = y_right
    for inset, kind in zoom_kinds:
        inset.kind = kind


def _check_x(panel: Panel, series: Series) -> None:
    if panel.x_axis is None:
        return
    source = series.data.x_quantity
    if source not in X_QUANTITIES or panel.x_axis.quantity not in X_QUANTITIES:
        raise IncompatibleXQuantity(
            f"{source.value} cannot be shown on a {panel.x_axis.quantity.value} axis"
        )


def _check_y(panel: Panel, key: CompatibilityKey) -> Ok | NeedsYChoice:
    if panel.y_left is None:
        return Ok(Side.LEFT)
    left_keys = {
        compatibility_key(L) for L in panel.layers if L.y_axis_side is Side.LEFT
    }
    if panel.y_left.arrangement.normalised or left_keys == {key}:
        return Ok(Side.LEFT)
    if panel.y_right is not None:
        right_keys = {
            compatibility_key(L) for L in panel.layers if L.y_axis_side is Side.RIGHT
        }
        if panel.y_right.arrangement.normalised or right_keys == {key}:
            return Ok(Side.RIGHT)
    if panel.y_left.arrangement.stacked:
        return NeedsYChoice((YChoice.NORMALISE,))
    return NeedsYChoice((YChoice.NORMALISE, YChoice.DUAL_AXIS))


def _plan_dual(panel: Panel, layers: Sequence[Layer], sides: dict[str, Side]) -> _YPlan:
    """Plan for option (b): each side raw if compatible, normalised otherwise (§6).

    Choosing sides lays the axes out anew, so a side's earlier normalisation is not
    carried over; removing a layer, by contrast, keeps it (Rob, S008).
    """
    current = _current_plan(panel)
    if current.left.stacked or current.right.stacked:
        raise StackedWithDualAxis(
            "a stacked panel cannot have a second y axis; unstack it first"
        )
    arrangements: dict[Side, LayerArrangement] = {}
    for side, before in ((Side.LEFT, current.left), (Side.RIGHT, current.right)):
        keys = {compatibility_key(L) for L in layers if sides[L.id] is side}
        normalised = len(keys) > 1
        arrangements[side] = dataclasses.replace(before, normalised=normalised)
    return _YPlan(
        sides=sides,
        left=arrangements[Side.LEFT],
        right=arrangements[Side.RIGHT],
        left_template=current.left_template,
        right_template=current.right_template,
    )


def _plan_normalise(panel: Panel, layers: Sequence[Layer]) -> _YPlan:
    current = _current_plan(panel)
    return _YPlan(
        sides={L.id: Side.LEFT for L in layers},
        left=dataclasses.replace(current.left, normalised=True),
        right=OVERLAP,
        left_template=current.left_template,
        right_template=None,
    )


def _insert_layer(panel: Panel, layer: Layer, resolution: Resolution | None) -> Layer:
    if panel.is_empty:
        domain = domain_of(layer.source)
        data = layer.source.data
        x_axis = XAxis(
            quantity=data.x_quantity,
            unit=data.x_unit,
            # Display default, not a guess: the user declared the technique (§5).
            inverted=domain is Technique.IR,
        )
        plan = _YPlan({layer.id: Side.LEFT}, OVERLAP, OVERLAP, None, None)
        zoom_kinds = _convert_zoom_regions(panel.insets, x_axis.unit)
        _commit(panel, [layer], plan, x_axis=x_axis, zoom_kinds=zoom_kinds)
        return layer
    _check_x(panel, layer.source)
    check = _check_y(panel, compatibility_key(layer))
    layers = [*panel.layers, layer]
    if isinstance(check, Ok):
        plan = _current_plan(panel)
        plan.sides[layer.id] = check.side
    elif resolution is None:
        raise YChoiceRequired(
            f"{layer.source.name!r} does not fit the y axis; choose to normalise or "
            "to use a second y axis"
        )
    elif isinstance(resolution, Normalise):
        plan = _plan_normalise(panel, layers)
    else:
        sides = {L.id: L.y_axis_side for L in panel.layers}
        for layer_id, side in resolution.sides.items():
            if layer_id not in sides:
                raise UnknownItem(f"no layer with id {layer_id} on this panel")
            sides[layer_id] = side
        sides[layer.id] = resolution.new_side
        plan = _plan_dual(panel, layers, sides)
    _commit(panel, layers, plan)
    return layer


def _convert_zoom_regions(
    insets: Sequence[Inset], unit: Unit
) -> list[tuple[Inset, ZoomInset]]:
    """Return each zoom inset with its region converted to ``unit`` (N2).

    Nothing is changed here; :func:`_commit` writes the new kinds into the same
    inset objects, so references held by the GUI stay valid.
    """
    return [
        (inset, dataclasses.replace(inset.kind, region=inset.kind.region.to(unit)))
        for inset in insets
        if isinstance(inset.kind, ZoomInset)
    ]


def _replace_layer(panel: Panel, layer: Layer, **changes: object) -> None:
    """Check a change of one layer's parameters against the panel, then apply it."""
    _require_layer(panel, layer)
    candidate = dataclasses.replace(layer, **changes)  # type: ignore[arg-type]
    layers = [candidate if L is layer else L for L in panel.layers]
    _commit_candidate(panel, layers)
    for name, value in changes.items():
        setattr(layer, name, value)


def _commit_candidate(panel: Panel, layers: list[Layer]) -> None:
    # Dry run on candidate objects; the real panel is untouched if this raises.
    plan = _current_plan(panel)
    y_left, y_right, sides = _compute_y(layers, plan)
    assert panel.x_axis is not None
    _validate_values(layers, sides, panel.x_axis, y_left, y_right)
    for layer in panel.layers:
        layer.y_axis_side = sides[layer.id]
    panel.y_left, panel.y_right = y_left, y_right


# --------------------------------------------------------------------------------
# Project and canvas
# --------------------------------------------------------------------------------


def new_project() -> Project:
    """Return a project with one canvas holding one empty panel."""
    project = Project()
    add_canvas(project)
    return project


def add_canvas(project: Project, name: str | None = None) -> Canvas:
    """Add a new canvas with a 1 × 1 grid and one empty panel (G3)."""
    canvas = Canvas(name=name or f"Canvas {len(project.canvases) + 1}")
    project.canvases.append(canvas)
    return canvas


def _require_canvas(project: Project, canvas: Canvas) -> None:
    if not any(item is canvas for item in project.canvases):
        raise UnknownItem(f"canvas {canvas.name!r} is not in this project")


def remove_canvas(project: Project, canvas: Canvas) -> None:
    """Remove ``canvas`` from ``project``."""
    _require_canvas(project, canvas)
    project.canvases = [c for c in project.canvases if c is not canvas]


def rename_canvas(canvas: Canvas, name: str) -> None:
    """Rename a canvas. The name cannot be blank."""
    if not name.strip():
        raise InvalidData("a canvas name cannot be blank")
    canvas.name = name


def set_canvas_size(canvas: Canvas, width_cm: float, height_cm: float) -> None:
    """Set the figure size in centimetres (both > 0)."""
    checked = Canvas(name=canvas.name, size_cm=(width_cm, height_cm))
    canvas.size_cm = checked.size_cm


def set_grid(canvas: Canvas, grid: Grid) -> None:
    """Replace the layout of ``canvas``. ``grid`` was validated when built (G1, G2)."""
    if not isinstance(grid, Grid):
        raise InvalidData("set_grid needs a Grid")
    canvas.grid = grid


def set_align_rows(canvas: Canvas, align: bool) -> None:
    """Give the drawing areas of one grid row the same height, or not."""
    canvas.align_rows = bool(align)


# --------------------------------------------------------------------------------
# Panel and layers
# --------------------------------------------------------------------------------


def check_add_layer(
    panel: Panel, series: Series, y_transforms: Sequence[YTransform] = ()
) -> Ok | NeedsYChoice:
    """Tell whether ``series`` fits the panel as it is, or needs the user's choice.

    Raises
    ------
    IncompatibleXQuantity
        The series' x cannot be converted to the panel's x quantity.
    """
    _check_x(panel, series)
    key = (domain_of(series), transformed_quantity(series, tuple(y_transforms)))
    return _check_y(panel, key)


def add_layer(
    panel: Panel,
    series: Series,
    resolution: Resolution | None = None,
    broadening: Broadening | None = None,
    y_transforms: Sequence[YTransform] = (),
) -> Layer:
    """Add ``series`` as a new layer at the top of the drawing order.

    The first layer of an empty panel sets its axes (§5). Later layers are converted
    to the panel's x unit; if their y does not fit, ``resolution`` says what the user
    chose.

    Raises
    ------
    MissingBroadening
        ``series`` holds sticks and no broadening is given.
    IncompatibleXQuantity
        The series' x cannot be converted to the panel's x quantity.
    YChoiceRequired
        The y does not fit and no resolution is given.
    StackedWithDualAxis
        ``DualAxis`` was asked for on a stacked panel.
    """
    layer = Layer(
        source=series,
        broadening=broadening,
        y_transforms=tuple(y_transforms),
        style=default_style(len(panel.layers)),
    )
    return _insert_layer(panel, layer, resolution)


def paste_layer(
    layer: Layer, target_panel: Panel, resolution: Resolution | None = None
) -> Layer:
    """Add an independent copy of ``layer`` to ``target_panel``.

    The copy has a new id and its own parameters; it shares the immutable source.
    """
    copy = Layer(
        source=layer.source,
        broadening=layer.broadening,
        crop=layer.crop,
        y_transforms=layer.y_transforms,
        stack_gap=layer.stack_gap,
        style=layer.style,
        id=new_id(),
    )
    return _insert_layer(target_panel, copy, resolution)


def remove_layer(panel: Panel, layer: Layer) -> None:
    """Remove ``layer``; removing the last one empties the panel (P1)."""
    _require_layer(panel, layer)
    layers = [L for L in panel.layers if L is not layer]
    _commit(panel, layers, _current_plan(panel))


def move_layer(panel: Panel, layer: Layer, new_index: int) -> None:
    """Move ``layer`` to position ``new_index`` of the drawing order."""
    _require_layer(panel, layer)
    if not 0 <= new_index < len(panel.layers):
        raise InvalidData(f"position {new_index} is outside 0–{len(panel.layers) - 1}")
    layers = [L for L in panel.layers if L is not layer]
    layers.insert(new_index, layer)
    _commit(panel, layers, _current_plan(panel))


def assign_y_axis_sides(panel: Panel, assignment: Mapping[str, Side]) -> None:
    """Put layers (by id) on the left or right y axis, as in option (b) of §6."""
    _require_x_axis(panel)
    sides = {L.id: L.y_axis_side for L in panel.layers}
    for layer_id, side in assignment.items():
        if layer_id not in sides:
            raise UnknownItem(f"no layer with id {layer_id} on this panel")
        sides[layer_id] = side
    _commit(panel, list(panel.layers), _plan_dual(panel, panel.layers, sides))


# --------------------------------------------------------------------------------
# Layer parameters
# --------------------------------------------------------------------------------


def set_broadening(layer: Layer, broadening: Broadening) -> None:
    """Replace the broadening parameters of a stick layer."""
    check_broadening(layer.source, broadening)
    layer.broadening = broadening


def set_crop(panel: Panel, layer: Layer, interval: Interval | None) -> None:
    """Keep only the part of the layer's data inside ``interval`` (``None``: all).

    Raises
    ------
    EmptySelection
        Too few points remain.
    """
    if interval is not None:
        crop(layer.source.data, interval)
    _replace_layer(panel, layer, crop=interval)


def add_y_transform(
    panel: Panel, layer: Layer, transform: YTransform, index: int | None = None
) -> None:
    """Insert ``transform`` into the layer's chain (at the end by default)."""
    if not isinstance(transform, YTransform):
        raise InvalidData("add_y_transform needs a YTransform")
    chain = list(layer.y_transforms)
    chain.insert(len(chain) if index is None else index, transform)
    _replace_layer(panel, layer, y_transforms=tuple(chain))


def remove_y_transform(panel: Panel, layer: Layer, index: int) -> None:
    """Remove the transform at ``index`` of the layer's chain."""
    chain = list(layer.y_transforms)
    if not 0 <= index < len(chain):
        raise InvalidData(f"the layer has no transform at position {index}")
    del chain[index]
    _replace_layer(panel, layer, y_transforms=tuple(chain))


def move_y_transform(panel: Panel, layer: Layer, old: int, new: int) -> None:
    """Move a transform of the layer's chain from ``old`` to ``new``."""
    chain = list(layer.y_transforms)
    if not (0 <= old < len(chain) and 0 <= new < len(chain)):
        raise InvalidData(f"positions must be within 0–{len(chain) - 1}")
    chain.insert(new, chain.pop(old))
    _replace_layer(panel, layer, y_transforms=tuple(chain))


def set_style(layer: Layer, style: Style) -> None:
    """Replace the display options of ``layer``."""
    if not isinstance(style, Style):
        raise InvalidData("set_style needs a Style")
    layer.style = style


def set_stack_gap(layer: Layer, gap: float | None) -> None:
    """Override the side's stack gap for ``layer`` (``None``: use the side's)."""
    layer.stack_gap = None if gap is None else check_gap(gap)


# --------------------------------------------------------------------------------
# Axes
# --------------------------------------------------------------------------------


def set_x_quantity(panel: Panel, quantity: Quantity, unit: Unit) -> None:
    """Change what the x axis shows; every layer, limit, break and zoom region follows.

    Inversion and the secondary axis are the user's choices and are kept.
    """
    x_axis = _require_x_axis(panel)
    check_x_unit(quantity, unit)
    new_x = dataclasses.replace(
        x_axis,
        quantity=quantity,
        unit=unit,
        limits=_convert_limits(x_axis.limits, x_axis.quantity, quantity),
        breaks=tuple(sorted((b.to(unit) for b in x_axis.breaks), key=lambda b: b.low)),
    )
    zoom_kinds = _convert_zoom_regions(panel.insets, unit)
    _commit(
        panel,
        list(panel.layers),
        _current_plan(panel),
        x_axis=new_x,
        zoom_kinds=zoom_kinds,
    )


def set_x_limits(panel: Panel, limits: tuple[float, float] | None) -> None:
    """Set the x view limits (``None``: automatic). Display only."""
    x_axis = _require_x_axis(panel)
    checked = None if limits is None else check_view_limits(*limits)
    panel.x_axis = dataclasses.replace(x_axis, limits=checked)


def set_x_inverted(panel: Panel, inverted: bool) -> None:
    """Draw x from high to low, or not."""
    x_axis = _require_x_axis(panel)
    panel.x_axis = dataclasses.replace(x_axis, inverted=bool(inverted))


def set_secondary_x(panel: Panel, quantity: Quantity | None, unit: Unit | None) -> None:
    """Show a second x scale under the main one, or remove it (both ``None``)."""
    x_axis = _require_x_axis(panel)
    if quantity is None or unit is None:
        if quantity is not None or unit is not None:
            raise InvalidData("give both the quantity and the unit, or neither")
        secondary = None
    else:
        check_x_unit(quantity, unit)
        secondary = (quantity, unit)
    panel.x_axis = dataclasses.replace(x_axis, secondary=secondary)


def _x_range(panel: Panel, x_axis: XAxis) -> tuple[float, float]:
    lows, highs = [], []
    for layer in panel.layers:
        data = layer.source.data
        x, _ = convert_x(data.x, data.y, data.x_quantity, x_axis.quantity)
        lows.append(float(x[0]))
        highs.append(float(x[-1]))
    return min(lows), max(highs)


def set_breaks(panel: Panel, breaks: Sequence[Interval]) -> None:
    """Store x axis breaks (v1.1 feature; validated and stored in v1.0, §11).

    Raises
    ------
    InvalidInterval
        Breaks overlap or fall outside the data range.
    """
    x_axis = _require_x_axis(panel)
    converted = sorted((b.to(x_axis.unit) for b in breaks), key=lambda b: b.low)
    for before, after in zip(converted, converted[1:], strict=False):
        if not before.high < after.low:
            raise InvalidInterval("axis breaks must not overlap")
    if converted:
        low, high = _x_range(panel, x_axis)
        for b in converted:
            if b.low < low or b.high > high:
                raise InvalidInterval(
                    f"break {b.low:g}–{b.high:g} {b.unit.value} is outside the data "
                    f"range {low:g}–{high:g}"
                )
    panel.x_axis = dataclasses.replace(x_axis, breaks=tuple(converted))


def _set_y(panel: Panel, side: Side, axis: YAxis) -> None:
    if side is Side.LEFT:
        panel.y_left = axis
    else:
        panel.y_right = axis


def set_y_limits(panel: Panel, side: Side, limits: tuple[float, float] | None) -> None:
    """Set the view limits of one y axis (``None``: automatic). Display only."""
    axis = _require_y_axis(panel, side)
    checked = None if limits is None else check_view_limits(*limits)
    _set_y(panel, side, dataclasses.replace(axis, limits=checked))


def set_y_inverted(panel: Panel, side: Side, inverted: bool) -> None:
    """Draw one y axis from high to low, or not."""
    axis = _require_y_axis(panel, side)
    _set_y(panel, side, dataclasses.replace(axis, inverted=bool(inverted)))


def set_y_scale(panel: Panel, side: Side, scale: Scale) -> None:
    """Show one y axis on a linear or logarithmic scale. Display only."""
    axis = _require_y_axis(panel, side)
    _set_y(panel, side, dataclasses.replace(axis, scale=Scale(scale)))


def set_arrangement(panel: Panel, side: Side, arrangement: LayerArrangement) -> None:
    """Set overlap, normalised overlap or stacked for one y side (§7).

    Raises
    ------
    StackedWithDualAxis
        Stacking was asked for on a panel with two y axes.
    IncompatibleYQuantity
        Normalisation was turned off on a side whose layers do not share a y.
    """
    _require_y_axis(panel, side)
    plan = _current_plan(panel)
    if side is Side.LEFT:
        plan.left = arrangement
    else:
        plan.right = arrangement
    _commit(panel, list(panel.layers), plan)


def set_axis_title(panel: Panel, axis: Side | None, title: str | None) -> None:
    """Set the title of the x axis (``axis=None``) or of one y axis."""
    if axis is None:
        x_axis = _require_x_axis(panel)
        panel.x_axis = dataclasses.replace(x_axis, title=title)
    else:
        y_axis = _require_y_axis(panel, axis)
        _set_y(panel, axis, dataclasses.replace(y_axis, title=title))


# --------------------------------------------------------------------------------
# Insets
# --------------------------------------------------------------------------------


def _require_inset_host(panel: Panel) -> None:
    if panel.is_inset:
        raise NestedInset("an inset cannot contain an inset")


def _check_region(panel: Panel, region: Interval) -> Interval:
    x_axis = _require_x_axis(panel)
    own = region.to(x_axis.unit)
    for b in x_axis.breaks:
        if b.low <= own.low and own.high <= b.high:
            raise RegionInBreak("the zoom region lies inside an axis break")
    return own


def _require_inset(panel: Panel, inset: Inset) -> None:
    if not any(item is inset for item in panel.insets):
        raise UnknownItem("the inset is not on this panel")


def add_zoom_inset(
    panel: Panel,
    region: Interval,
    placement: Placement,
    y_limits: tuple[float, float] | None = None,
) -> Inset:
    """Add a live zoom of ``region`` of the host panel (N2, N3)."""
    _require_inset_host(panel)
    own = _check_region(panel, region)
    limits = None if y_limits is None else check_view_limits(*y_limits)
    inset = Inset(placement=placement, kind=ZoomInset(region=own, y_limits=limits))
    panel.insets.append(inset)
    return inset


def add_free_inset(panel: Panel, inner: Panel, placement: Placement) -> Inset:
    """Place the full panel ``inner`` inside ``panel`` (N1)."""
    _require_inset_host(panel)
    if inner is panel:
        raise InvalidData("a panel cannot be an inset of itself")
    if inner.insets:
        raise NestedInset("a panel that holds insets cannot become an inset")
    if inner.is_inset:
        raise InvalidData("that panel is already an inset of another panel")
    inset = Inset(placement=placement, kind=FreeInset(panel=inner))
    inner.is_inset = True
    panel.insets.append(inset)
    return inset


def set_inset_placement(panel: Panel, inset: Inset, placement: Placement) -> None:
    """Move or resize an inset."""
    _require_inset(panel, inset)
    inset.placement = check_placement(placement)


def set_zoom_region(panel: Panel, inset: Inset, region: Interval) -> None:
    """Change the region shown by a zoom inset."""
    _require_inset(panel, inset)
    if not isinstance(inset.kind, ZoomInset):
        raise InvalidData("only a zoom inset has a region")
    own = _check_region(panel, region)
    inset.kind = dataclasses.replace(inset.kind, region=own)


def remove_inset(panel: Panel, inset: Inset) -> None:
    """Remove an inset; a free inset's panel becomes a normal panel again."""
    _require_inset(panel, inset)
    panel.insets = [i for i in panel.insets if i is not inset]
    if isinstance(inset.kind, FreeInset):
        inset.kind.panel.is_inset = False


__all__ = [
    "DualAxis",
    "NeedsYChoice",
    "Normalise",
    "Ok",
    "Resolution",
    "YChoice",
    "add_canvas",
    "add_free_inset",
    "add_layer",
    "add_y_transform",
    "add_zoom_inset",
    "assign_y_axis_sides",
    "check_add_layer",
    "move_layer",
    "move_y_transform",
    "new_project",
    "paste_layer",
    "remove_canvas",
    "remove_inset",
    "remove_layer",
    "remove_y_transform",
    "rename_canvas",
    "set_align_rows",
    "set_arrangement",
    "set_axis_title",
    "set_breaks",
    "set_broadening",
    "set_canvas_size",
    "set_crop",
    "set_grid",
    "set_secondary_x",
    "set_stack_gap",
    "set_style",
    "set_x_inverted",
    "set_x_limits",
    "set_x_quantity",
    "set_y_inverted",
    "set_y_limits",
    "set_y_scale",
]
