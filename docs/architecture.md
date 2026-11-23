# Architecture

Status: **approved** by Rob (task T1.1, session S006, 2026-11-15).
Terms are used as defined in [`glossary.md`](glossary.md).

This document fixes the data model of `graphing`: the classes, their fields and
invariants, how data flows from a file to the values on screen, which combinations
are allowed, and which operations the GUI may call. Tasks T1.2–T1.6 implement it;
they may add private helpers but not change what is written here without a new
decision (R9).

Contents

1. Layers of the code
2. Design principles
3. Value objects (immutable)
4. Containers (mutable)
5. The inheritance rule
6. Y compatibility and the double y axis
7. Layer arrangement
8. The evaluation pipeline
9. Combination rules
10. Worked examples, one per figure type
11. Breaks (reserved for v1.1)
12. Operations exposed to the GUI
13. Named errors
14. Decisions and discarded alternatives
15. Points left for review

---

## 1. Layers of the code

```
gui/  ──calls──▶  core/ operations  ──mutate──▶  core/ model
 │                                                 │
 └──asks to redraw──▶  render/  ──reads──▶  model + core/ evaluation
```

- `core/` holds the model, the operations and every calculation. It imports nothing
  from `render/` or `gui/`.
- `render/` turns a `Canvas` into a Matplotlib `Figure`. It asks `core/` for the
  values to draw (§8) and never computes them itself. It imports nothing from `gui/`.
- `gui/` shows widgets, collects the user's choices and calls the operations of §12.
  It never writes a model field directly.

## 2. Design principles

- **Data objects are immutable; containers are mutable.** A `Series`, a `Broadening`
  or a transform never changes after construction. A `Layer`, `Panel`, `Canvas` or
  `Project` changes, but only through the operations of §12.
- **Raw arrays are never copied without need.** Several layers built from the same
  file share the same `Series` object. Changing the FWHM of a layer replaces a
  three-number `Broadening`, not the arrays. Because a `Series` is immutable, sharing
  it is safe: a pasted layer is still an independent copy (§12).
- **Everything shown is recomputed from raw data plus parameters** (§8). Nothing
  derived is stored in the model.
- **The model is generic; the product is about spectra** (D-20261115-01). The base
  data type is a generic x–y `Series`; `Spectrum` specialises it. v1.0 exposes only
  spectra in the GUI.
- **Core never asks the user.** When a choice is needed (§6), core reports the
  options and the GUI asks; then the GUI calls the operation with the choice.
- **Plain data.** Every field is a number, string, enum, tuple, array or another
  model object, so the project file (E11) can serialise the model without
  special cases.

## 3. Value objects (immutable)

Frozen dataclasses. Arrays are stored as read-only NumPy arrays
(`flags.writeable = False`); constructors copy the input once.

### 3.1 `Quantity` and `Unit`

A `Quantity` names what an axis measures; a `Unit` names how. Each quantity has a
fixed set of units and a default one. `core/units.py` (T1.2) owns the conversions.

| Quantity | Units | Used on |
|---|---|---|
| `WAVELENGTH` | nm | x |
| `WAVENUMBER` | cm⁻¹ | x |
| `ENERGY` | eV | x |
| `ABSORBANCE` | — | y |
| `TRANSMITTANCE` | % | y |
| `MOLAR_ABSORPTIVITY` | L mol⁻¹ cm⁻¹ | y |
| `INTENSITY` | arbitrary | y |
| `OSCILLATOR_STRENGTH` | — | y (sticks) |
| `IR_INTENSITY` | km mol⁻¹ | y (sticks) |
| `NORMALISED_INTENSITY` | — | y (result of normalisation only) |
| `GENERIC(name, unit)` | free text | x or y of a generic series |

`WAVELENGTH`, `WAVENUMBER` and `ENERGY` form one convertible family. Any other two
x quantities are convertible only if they are equal.

### 3.2 `CurveData` and `StickData`

Two distinct types (T1.3 AC3), same fields:

| Field | Type | Invariant |
|---|---|---|
| `x` | read-only float array | finite; curve: strictly ascending; sticks: any order, repeats allowed |
| `y` | read-only float array | finite, same length as `x`, length ≥ 1 (curve: ≥ 2) |
| `x_quantity`, `x_unit` | `Quantity`, `Unit` | unit belongs to quantity |
| `y_quantity`, `y_unit` | `Quantity`, `Unit` | unit belongs to quantity; never `NORMALISED_INTENSITY` |
| `labels` (sticks only) | `tuple[str, ...] \| None` | one per line (mode or state number); `None` = lines numbered 1…n in file order |

Readers that receive x descending (common in IR exports) reverse both arrays before
construction of a curve, keeping x–y pairs together.

**Stick lines are kept exactly as the program printed them** (D-20261118-02): every
line, in file order, with its label, repeated positions included. Equality and hash
include the order and the labels. Degeneracy is never stored: it is a view (§8.1).

### 3.3 `Series` and `Spectrum`

```
Series
  name: str                     shown in the legend by default
  data: CurveData | StickData
  metadata: Mapping[str, str]   file name, program, instrument, date…  (read-only)

Spectrum(Series)
  technique: Technique          UV_VIS | IR            declared by the user
  origin: Origin                THEORETICAL | EXPERIMENTAL   declared by the user
```

Invariants of `Spectrum`:
- `StickData` implies `origin = THEORETICAL`.
- The app never infers `technique` or `origin` and never warns about them (CLAUDE §6.3).

The **compatibility domain** of a series is `technique` for a `Spectrum` and `None`
for a generic `Series` (§6).

### 3.4 `Broadening`

```
Broadening
  line_shape: LineShape       GAUSSIAN | LORENTZIAN | VOIGT
  fwhm: float                 > 0; for VOIGT, the Gaussian width
  fwhm_unit: Unit             cm⁻¹ or eV (linear in energy; nm is refused, T3.2)
  scale_factor: float         > 0, default 1.0 (multiplies positions, T3.3)
  shift: float                finite, default 0.0, in fwhm_unit (added after scaling)
  step: float | None          > 0, in fwhm_unit; None = automatic (default)
  fwhm_lorentzian: float|None > 0, in fwhm_unit; required for VOIGT, None otherwise
```

Voigt's second width was added in T3.2 with a default of `None`, so no existing call
changes (option A, Rob S015). A FWHM in nm is not accepted: a constant width in nm is
not a constant width in energy (Rob S016).

`step` is the spacing of the x grid on which the broadened curve is computed. The
automatic value is the profile FWHM / 50 (Rob S016; for Voigt, the profile FWHM is
`voigt_fwhm`). Any step
much smaller than the FWHM gives a curve that looks the same on screen, so the
interface keeps `step` out of the way. Where the user will want it is **exporting the
broadened curve as data** (E11): the number of rows in the exported file depends on
it, so the export dialog shows the step in use and lets the user change it there.
The grid range (the outermost sticks ± 5 profile FWHMs, never reaching zero) is chosen
at evaluation time (§8) and not stored. A Lorentzian keeps about 94 % of its area
inside that range; the curve is exact at every grid point, and the range is a display
choice (Rob S016).

### 3.5 `Interval`

`Interval(low, high, quantity, unit)`, `low < high`. A range only: it has no step
and is never a list of points (sampling is a separate matter, §3.4 and §8).

Being immutable, an `Interval` is never changed in place: `interval.to(unit)` returns
a **new** `Interval`. Wavelength is inversely proportional to wavenumber and energy,
so converting between them reverses the order of the ends; the conversion swaps them
so that the new interval is again ascending:

```
Interval(400, 500, WAVELENGTH, nm).to(eV)
  → 400 nm = 3.0996 eV, 500 nm = 2.4797 eV
  → Interval(2.4797, 3.0996, ENERGY, eV)      low and high swapped
```

Conversions within one quantity (none in v1.0) and between wavenumber and energy
(directly proportional) keep the order.

### 3.6 Y transforms

One frozen class per transform (T1.4). Each has an `apply(x, y, x_quantity) -> y` method (`x_quantity` tells
`NormaliseAtX` what the x array measures) and a short label for the interface.

| Class | Parameters | Effect on the y quantity |
|---|---|---|
| `TransmittanceToAbsorbance` | — | `TRANSMITTANCE` → `ABSORBANCE` |
| `AbsorbanceToTransmittance` | — | `ABSORBANCE` → `TRANSMITTANCE` |
| `Log10` | — | quantity becomes `DerivedQuantity("log10", source)` |
| `Inverse` | — | quantity becomes `DerivedQuantity("inverse", source)` |
| `Level` | `constant: float` | unchanged |
| `NormaliseToMax` | — | `NORMALISED_INTENSITY` |
| `NormaliseAtX` | `x: float`, `quantity`, `unit` | `NORMALISED_INTENSITY` |

A `DerivedQuantity(operation, source)` is equal to another only with the same
operation and source; free-text `GENERIC` quantities are not in v1.0 (D-20261116-01).
`core.transforms.apply_transforms` applies a tuple in order to the raw arrays and
checks the y quantity at every step.

Each layer holds a tuple of these. The **effective y quantity** of a layer is the
source's y quantity after its transforms; that is what §6 compares.

### 3.7 `Style`

`colour` (hex), `line_width`, `line_style`, `label` (`None` = series name),
`visible`, and for sticks layers only `show_curve` and `show_sticks` (both default
`True`; at least one must be `True`). A sticks layer can therefore show the broadened
curve with its sticks (default), the curve alone, or the sticks alone. The broadening
is kept even while the curve is hidden. Default colours cycle through Rob's palette
(CLAUDE §7).

Sticks layers also have `sum_sticks` (default `True`, D-20261118-03, -04). It is
display only and changes no value: when `False`, lines not resolved at the current
zoom are drawn one by one, even if they overlap; lines with the same position are
still summed (§8.1). It is a user parameter, so it has a "?" help entry.

## 4. Containers (mutable)

Each container has a stable `id` (UUID string) so the GUI and the project file can
refer to it.

### 4.1 `Layer`

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | |
| `source` | `Series` | shared, never copied |
| `broadening` | `Broadening \| None` | required iff `source.data` is `StickData` |
| `crop` | `Interval \| None` | `None` = whole data |
| `y_transforms` | `tuple[YTransform, ...]` | applied in order |
| `y_axis_side` | `LEFT \| RIGHT` | which of the panel's y axes the layer is drawn against: left (default) or right in a double-y-axis panel (§6) |
| `stack_gap` | `float \| None` | override of the panel's gap (§7); `None` = use panel's |
| `style` | `Style` | |

### 4.2 `XAxis`

| Field | Type | Notes |
|---|---|---|
| `quantity`, `unit` | | set by the first layer (§5) |
| `limits` | `tuple[float, float] \| None` | view limits; `None` = automatic |
| `inverted` | `bool` | high to low, left to right |
| `secondary` | `tuple[Quantity, Unit] \| None` | secondary x axis, drawn under the main one |
| `breaks` | `tuple[Interval, ...]` | default `()`; reserved for v1.1 (§11) |
| `title` | `str \| None` | `None` = generated from quantity and unit |

### 4.3 `YAxis`

| Field | Type | Notes |
|---|---|---|
| `quantity`, `unit` | | `NORMALISED_INTENSITY` when `arrangement.normalised` |
| `domain` | `Technique \| None` | compatibility domain of its layers (§6) |
| `limits` | `tuple[float, float] \| None` | view limits |
| `inverted` | `bool` | high to low, bottom to top |
| `scale` | `LINEAR \| LOG` | |
| `arrangement` | `LayerArrangement` | §7 |
| `title` | `str \| None` | |

`LayerArrangement(normalised: bool, stacked: bool, gap: float | None)`. The three
named arrangements are:

| Name | `normalised` | `stacked` |
|---|---|---|
| Overlap | `False` | `False` |
| Normalised overlap | `True` | `False` |
| Stacked | either | `True` |

### 4.4 `Panel`

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | |
| `x_axis` | `XAxis \| None` | `None` while empty |
| `y_left` | `YAxis \| None` | `None` while empty |
| `y_right` | `YAxis \| None` | double y axis |
| `layers` | `list[Layer]` | drawing order = list order |
| `insets` | `list[Inset]` | |
| `title`, `legend` | | display options |

Invariants:
- **P1** Empty panel ⇔ no layers ⇔ `x_axis is None and y_left is None`.
- **P2** Every layer's x quantity is convertible to `x_axis.quantity`.
- **P3** Every layer on a side is compatible with that side's y axis, or that side is
  normalised (§6).
- **P4** `y_right is not None` ⇔ at least one layer has `y_axis_side = RIGHT`.
- **P5** Not both sides normalised (they collapse into one axis, §6).
- **P6** A stacked side excludes `y_right`.

### 4.5 `Inset`

```
Inset
  id: str
  placement: (x0, y0, width, height)   fractions of the host panel's drawing area
  kind: ZoomInset | FreeInset

ZoomInset
  region: Interval                     in the host's x quantity
  y_limits: tuple[float, float] | None
  (no layers, no axes of its own: it shows the host's layers, live)

FreeInset
  panel: Panel                         a full panel, with its own layers and axes
```

Invariants:
- **N1** A free inset's panel has no insets (an inset cannot contain an inset).
- **N2** A zoom inset's x quantity, unit, inversion and transforms are always those of
  the host. Changing the host's x unit converts `region`.
- **N3** A zoom inset shows the host's layers with the host's transforms and
  arrangement. Changing a FWHM in the host changes the inset.

### 4.6 `Canvas` and `Grid`

```
Canvas
  id, name: str
  size_cm: (width, height)
  grid: Grid
  align_rows: bool        drawing areas in one grid row get the same height

Grid
  column_widths: tuple[float, ...]   relative, > 0
  row_heights: tuple[float, ...]     relative, > 0
  cells: list[Cell]

Cell
  row, column: int
  row_span, column_span: int         ≥ 1
  content: Panel | Grid              a nested grid allows uneven splits
```

Invariants:
- **G1** Cells lie inside the grid and do not overlap.
- **G2** Every cell has content. Empty space is not a cell.
- **G3** A new canvas has a 1 × 1 grid with one empty panel.

Matplotlib supports this directly (`GridSpec` with `width_ratios`, `height_ratios`,
spans, and `subgridspec` for nesting).

### 4.7 `Project`

```
Project
  schema_version: int       independent of the app version (CLAUDE §9)
  canvases: list[Canvas]
  metadata: Mapping[str, str]
```

The `Series` objects are reachable through the layers. The project file (E11) stores
each distinct `Series` once and refers to it from every layer that uses it.

## 5. The inheritance rule

ggplot2 style:

1. The **first layer** added to an empty panel creates its axes. The x axis takes the
   layer's x quantity and unit. `y_left` takes its effective y quantity, unit and
   domain. The arrangement is overlap. Display defaults follow the technique the
   user declared for that first layer: an IR spectrum starts with the x axis inverted
   (high wavenumber on the left); a UV-Vis spectrum does not. These are defaults, not
   guesses: the user changes them freely, and later layers do not reset them.
2. Every **later layer** is converted to the panel's x unit. If its x quantity is not
   convertible (§3.1), the operation raises `IncompatibleXQuantity`. A convertible
   quantity is always accepted, even when the ranges do not overlap: a UV-Vis and an
   IR spectrum on one wavenumber axis show a large empty stretch, and that is the
   intended feedback to the student.
3. Its y is then checked against the panel's y axes (§6).
4. **Changing an axis quantity or unit** (from the axis title) converts every layer
   of the panel, and every zoom inset's region. Limits and breaks are converted too.
5. Removing the last layer returns the panel to the empty state (P1).

## 6. Y compatibility and the double y axis

Two layers are **compatible** when their compatibility keys are equal:

```
key(layer) = (domain of the source, effective y quantity of the layer)
```

So UV-Vis absorbance and IR absorbance are not compatible; UV-Vis absorbance and
UV-Vis absorbance from another file are. A transmittance layer turned into
absorbance with `TransmittanceToAbsorbance` is compatible with absorbance layers.

Each y side is in one of two states:

- **Raw:** all its layers share one key; the axis shows that quantity and unit.
- **Normalised:** its layers may have any keys; every layer is normalised (§7) and the
  axis shows "Normalised intensity".

When a layer is added and is compatible with `y_left` (or `y_left` is normalised), it
goes to the left side. Otherwise `check_add_layer` returns `NeedsYChoice` and the GUI
offers the two options agreed with Rob:

- **(a) Normalise:** one y axis, normalised; every layer goes to it.
- **(b) Double y axis:** the user assigns each layer of the panel to left or right.
  Each side then becomes raw if its layers are compatible, normalised otherwise.
  If both sides would be normalised, there is nothing to separate: the panel falls
  back to (a) (P5).

Option (b) is not offered when the left side is stacked (P6).

## 7. Layer arrangement

Let a y side hold layers `L₀, L₁, …, Lₙ` in drawing order, and `yᵢ` be the values of
`Lᵢ` after step 5 of §8.

**Normalisation (when `normalised`)**

```
yᵢ' = yᵢ / max(yᵢ)
```

The maximum is taken over the layer's data after crop, not over the current view, so
zooming never changes the values. `max(yᵢ) ≤ 0` raises `CannotNormalise`. A layer
whose own transforms already normalise it is not normalised twice.

**Stacking (when `stacked`)**

```
b₀ = 0
bᵢ = bᵢ₋₁ + gapᵢ            gapᵢ = Lᵢ.stack_gap or the side's gap
yᵢ'' = yᵢ' + bᵢ
```

Default gap: `1.1` when normalised; `1.1 × max over layers of max(yᵢ')` otherwise.
The user can change the gap for the whole side or for one layer (`stack_gap`).

**Overlap:** `yᵢ'' = yᵢ`.

## 8. The evaluation pipeline

`core.evaluate.layer_values(layer, panel) -> (x, y, sticks | None)` computes what a
layer shows. `render/` calls it and draws the result. Steps, in this fixed order:

| # | Step | Applies to | Notes |
|---|---|---|---|
| 1 | Read source arrays | all | |
| 2 | Correct stick positions: `x' = scale_factor·x + shift`, in `fwhm_unit` | sticks | D-20261122-07. Lines at or below zero before the correction are left alone; lines that end at or below zero are not drawn. In a nm view a constant shift in eV is not constant in nm (manual) |
| 3 | Broaden onto an x grid | sticks | grid spans the sticks ± a multiple of FWHM; uniform spacing `Broadening.step` in `fwhm_unit` |
| 4 | Crop | all | `Interval` converted to the data's unit; inclusive bounds |
| 5 | Convert x to the panel's x unit; apply `y_transforms` in order | all | x ascending, x–y pairs kept |
| 6 | Arrangement (§7): normalise, then offset | all | |

A grid uniform in the broadening unit is no longer uniform after step 5 converts x
to another unit (e.g. eV → nm). That is expected and harmless: the conversion keeps
every x–y pair, and the drawn curve is the same.

View limits, inversion, log scale, secondary x axis and breaks are display options:
`render/` applies them to the Matplotlib axes, and they never change the values.

Steps 1–5 depend only on the layer and the panel's x unit, so `core/` may cache them
per layer and invalidate the cache when the layer or the x unit changes. The cache
is an implementation detail, not part of the model.

For a sticks layer, `LayerValues.sticks` holds the lines after steps 1–6 as
`(x, y, line_index)`: `line_index` points into the source lines, so a drawn stick can
name the lines it stands for. The broadened curve is always computed from these raw
lines (step 3), never from summed sticks, and does not depend on the view.

The sticks go through the same steps as their curve (T3.2, Rob S016; restated in
D-20261122-08, which replaces D-20261122-05): crop, x conversion, and every y
transform, so that sticks and curve keep their shape relation. A **linear** transform
(f → ε, km/mol → ε, ε ↔ A by Beer–Lambert, normalise to maximum, normalise at x)
gives the same curve whether it acts on the lines before broadening or on the curve
after, and the sticks are scaled with it: normalisations divide the sticks by the
curve's divisor, Beer–Lambert multiplies or divides them by b·c, and a conversion to
ε takes each stick to the maximum of its band alone, K·h·g(0) (`docs/theory.md` §3).
Step 6 gives the sticks the same divisor and offset as the curve. A **non-linear**
transform (%T ↔ A, log, inverse, and levelling, which is affine) can only act on the
broadened curve, because broadening is a sum; it acts on each stick height as on one
value (from an ε or A stick, this is what its band alone would give at its
centre). A stick it
cannot take (log of 0, 1/0) is dropped, and the curve is still shown. Lines at or below zero (imaginary frequencies, recorded in the
metadata by the reader) are neither broadened nor drawn (Rob S016).

### 8.1 Summed sticks (display step)

Decisions D-20261118-02 to -05. After step 6, `render/` groups the stick lines of a
layer for drawing with the pure function `core.sticks.group_sticks(x, y,
line_index, resolution)`, in the displayed x unit:

1. Lines with the same position are always summed, at any zoom and whatever
   `sum_sticks` says (exact equality survives the scale factor, the shift and the unit
   conversion: the same operation on equal numbers gives equal numbers).
2. If `sum_sticks` is on, lines not resolved on the figure are summed too: sorted by
   position, a group starts at the lowest line not yet grouped and takes every line
   within `resolution` of it (width-limited, anchored, no chaining; stable under
   panning). `resolution` is a length on the figure, about 0.5 mm (2 px at 100 dpi),
   turned into x units from the view limits and the plot width, so an exported figure
   groups like the screen. Zooming in separates the lines.
3. Each `StickGroup` holds the position, the summed height, the members
   (`line_index` values) and whether the group is degenerate (one position) or
   unresolved. An unresolved group is drawn at the intensity-weighted centroid of its
   members; if the sum is 0, at the tallest member (ties: first in file order).
4. A summed stick has its tip, about 1 mm, in a lighter tone of the layer colour; the
   same mark for both kinds. Selecting it says "sum of g degenerate lines" or "n lines
   not resolved at this zoom", with the range and the members.

Grouping never feeds back into values: normalisation, stacking, peaks, the project
file and data export use the raw lines. Exporting stick lines writes every original
line in file order with its label, its printed position and its position after the
scale factor and shift.

Prototype on real data (local, unpublished): `logbook-files/S014-X03/`.

## 9. Combination rules

| Combination | Allowed | If not: error |
|---|---|---|
| Overlap, normalised overlap, stacked on one panel side | one at a time | — |
| Stacked + normalised | yes | — |
| Stacked + double y axis | no | `StackedWithDualAxis` |
| Double y axis, both sides normalised | collapses to one normalised axis | — |
| Inset inside an inset | no | `NestedInset` |
| Zoom inset on a panel with any arrangement or double axis | yes; mirrors the host | — |
| Free inset with any arrangement or double axis | yes; it is a full panel | — |
| Subplots with anything | yes; each panel is independent | — |
| Secondary x axis with anything | yes | — |
| X quantities not convertible on one panel | no | `IncompatibleXQuantity` |
| Breaks (v1.1) with a zoom region inside a break | no | `RegionInBreak` |

## 10. Worked examples, one per figure type

Notation: Python-like constructors; omitted fields take their defaults.
`uv_exp`, `uv_th`, `ir_exp` are `Spectrum` objects read from files.

### 10.1 Overlap

Two experimental UV-Vis spectra in absorbance.

```
a = Spectrum(technique=UV_VIS, origin=EXPERIMENTAL, data=CurveData(x nm, y ABSORBANCE))
b = Spectrum(same technique and quantity, another file)
panel = Panel()
add_layer(panel, a)  → x_axis = XAxis(WAVELENGTH, nm); y_left = YAxis(ABSORBANCE, domain=UV_VIS)
add_layer(panel, b)  → compatible; goes left; overlap
```

### 10.2 Normalised overlap

Experimental UV-Vis absorbance plus a theoretical UV-Vis spectrum (oscillator
strengths, broadened).

```
add_layer(panel, uv_exp)
check_add_layer(panel, uv_th) → NeedsYChoice   (ABSORBANCE ≠ OSCILLATOR_STRENGTH)
user picks (a):
add_layer(panel, uv_th, resolution=Normalise(),
          broadening=Broadening(GAUSSIAN, fwhm=0.3, fwhm_unit=eV))
→ y_left = YAxis(NORMALISED_INTENSITY, arrangement=LayerArrangement(normalised=True, stacked=False))
  uv_th's sticks are converted from eV to nm at step 5; both curves have max 1
```

### 10.3 Stacking

Four IR spectra of a series of compounds, normalised and stacked.

```
for s in (ir1, ir2, ir3, ir4): add_layer(panel, s)
set_arrangement(panel, LEFT, LayerArrangement(normalised=True, stacked=True, gap=None))
→ baselines 0, 1.1, 2.2, 3.3
set_stack_gap(panel.layers[2], 1.5)   → baselines 0, 1.1, 2.6, 3.7
x axis already inverted: the first layer is IR (§5)
```

### 10.4 Double y axis

Rob's example: experimental UV-Vis (absorbance), experimental IR (absorbance),
theoretical UV-Vis (oscillator strength). All three keys differ.

```
add_layer(panel, uv_exp)
check_add_layer(panel, ir_exp) → NeedsYChoice;  user picks (b)
add_layer(panel, ir_exp, resolution=DualAxis({uv_exp: LEFT, ir_exp: RIGHT}))
→ y_left  = YAxis(ABSORBANCE, domain=UV_VIS)      raw
  y_right = YAxis(ABSORBANCE, domain=IR)          raw
check_add_layer(panel, uv_th) → NeedsYChoice;  user picks (b), assigns it LEFT
→ y_left  = YAxis(NORMALISED_INTENSITY)           two keys on the left: normalised
  y_right = YAxis(ABSORBANCE, domain=IR)          still raw
Had the user put uv_th on the RIGHT, the right side would be normalised and the left raw.
Had both sides needed normalising, the panel would fall back to one normalised axis.
```

The x axis is shared: UV-Vis in nm and IR in cm⁻¹ are converted to the first
layer's unit (nm), and the plot shows the large gap between their ranges.

### 10.5 Subplots

Rob's layout: a 20 × 20 cm canvas; one panel 10 wide × 20 high on the left; on the
right, panels 7 and 13 high.

```
Canvas(size_cm=(20, 20), grid=Grid(
    column_widths=(1, 1),
    row_heights=(7, 13),
    cells=[Cell(0, 0, row_span=2, content=P1),
           Cell(0, 1, content=P2),
           Cell(1, 1, content=P3)]))
```

An uneven split such as "left column 7 / 13, right column 5 / 15" uses nested grids:

```
Grid(column_widths=(1, 1), row_heights=(1,), cells=[
    Cell(0, 0, content=Grid(column_widths=(1,), row_heights=(7, 13), cells=[…])),
    Cell(0, 1, content=Grid(column_widths=(1,), row_heights=(5, 15), cells=[…]))])
```

### 10.6 Inset

**Zoom inset.** A detail of the 450–520 nm region of the panel of 10.2.

```
add_zoom_inset(panel, region=Interval(450, 520, WAVELENGTH, nm),
               placement=(0.55, 0.50, 0.40, 0.40))
→ Inset(kind=ZoomInset(region=…, y_limits=None))
change_broadening(panel.layers[1], fwhm=0.2)   → host and inset both redraw (N3)
set_x_unit(panel, cm⁻¹)                        → region becomes 19 231–22 222 cm⁻¹ (N2)
```

The GUI shows the region in a temporary panel for adjustment before placing it;
that temporary view is a GUI matter, not a model object.

**Free inset.** A small IR spectrum inside a UV-Vis panel.

```
inner = Panel(); add_layer(inner, ir_exp)
add_free_inset(panel, inner, placement=(0.05, 0.55, 0.35, 0.40))
add_free_inset(inner, …) → NestedInset
```

### 10.7 Transformed axes

An experimental IR spectrum exported in transmittance, shown as absorbance, with
wavenumber inverted and wavelength underneath.

```
add_layer(panel, ir_T)                                 → y_left = TRANSMITTANCE,
                                                         x inverted (IR default)
add_y_transform(panel.layers[0], TransmittanceToAbsorbance())
                                                       → y_left = ABSORBANCE
set_secondary_x(panel, WAVELENGTH, µm or nm)           → display only
```

A log y axis is either `YAxis.scale = LOG` (display) or a `Log10` transform (values);
the first keeps the quantity, the second changes it (§3.6).

### 10.8 Gap (reserved)

See §11.

## 11. Breaks (reserved for v1.1)

`XAxis.breaks` exists from v1.0 with default `()`, so adding breaks in v1.1 changes
no class signature (AC2).

```
set_breaks(panel, (Interval(1800, 2500, WAVENUMBER, cm⁻¹),))
```

- **Model:** still one panel, one x axis, the same layers. Arrangement, normalisation
  and peak picking do not know about breaks: a break hides, it does not remove data.
- **Render (v1.1):** for a panel with N breaks, `render/` creates N + 1 Matplotlib
  axes side by side, sharing y, each with x limits between two breaks, inner spines
  hidden and diagonal marks at the joins. Every sub-axis draws the same layer values.
  This is the standard Matplotlib recipe; Matplotlib has no native broken axis.
- **v1.0:** `set_breaks` validates its input (sorted, non-overlapping, inside the data
  range) and stores it; the GUI offers no control; `render/` raises
  `FeatureNotAvailable` if it meets a non-empty `breaks`.

## 12. Operations exposed to the GUI

All live in `core/operations.py` (or a small package), take model objects plus plain
parameters, and either succeed or raise a named error (§13) leaving the model
unchanged.

**Project and canvas**
`new_project()`, `add_canvas(project)`, `remove_canvas`, `rename_canvas`,
`set_canvas_size`, `set_grid(canvas, grid)`, `set_align_rows`.

**Panel and layers**
`check_add_layer(panel, series) -> Ok | NeedsYChoice`,
`add_layer(panel, series, resolution=None, broadening=None) -> Layer`,
`remove_layer`, `move_layer(panel, layer, new_index)`,
`paste_layer(layer, target_panel, resolution=None) -> Layer`
(new `id`, copied parameters, same shared `Series`; independent from the original),
`assign_y_axis_sides(panel, assignment)`.

**Layer parameters**
`set_broadening(layer, broadening)`, `set_crop(layer, interval | None)`,
`add_y_transform`, `remove_y_transform`, `move_y_transform`,
`set_style(layer, style)`, `set_stack_gap(layer, gap | None)`.

**Axes**
`set_x_quantity(panel, quantity, unit)`, `set_x_limits`, `set_x_inverted`,
`set_secondary_x(panel, quantity | None, unit | None)`, `set_breaks`,
`set_y_limits(panel, side, limits)`, `set_y_inverted`, `set_y_scale`,
`set_arrangement(panel, side, arrangement)`, `set_axis_title`.

**Insets**
`add_zoom_inset(panel, region, placement)`, `add_free_inset(panel, inner, placement)`,
`set_inset_placement`, `set_zoom_region`, `remove_inset`.

**Evaluation (read-only, used by `render/` and by peak picking)**
`layer_values(layer, panel)`, `y_axis_state(panel, side)`.

## 13. Named errors

All derive from `GraphingError`, carry a message that names what was wrong, and are
translatable through the GUI.

`IncompatibleXQuantity`, `StackedWithDualAxis`, `NestedInset`, `CannotNormalise`,
`EmptySelection`, `NonPositiveValue`, `InvalidInterval`, `GridOverlap`,
`MissingBroadening`, `RegionInBreak`, `FeatureNotAvailable`, `InvalidData`,
`InvalidUnit` (added in T1.3), `InvalidTransform`, `DivisionByZero` (added in T1.4). `InvalidInterval` and
`EmptySelection` are implemented in T1.5. T1.6 implements `StackedWithDualAxis`,
`NestedInset`, `GridOverlap`, `MissingBroadening`, `RegionInBreak` and
`FeatureNotAvailable`, and adds `IncompatibleYQuantity` (layers of different y on a
side that is not normalised), `YChoiceRequired` (a layer that needs the choice of §6
added without one), `EmptyPanel` (an axis operation on a panel with no layers) and
`UnknownItem` (a layer, inset or canvas that is not where it was looked for).
Later tasks may add errors; each is listed here when added.

## 14. Decisions and discarded alternatives

| Choice | Alternative discarded | Why |
|---|---|---|
| Immutable data, mutable containers | Fully immutable model (every edit builds a new `Project`) | Rob, S006: spectra are edited constantly; one new instance per edit costs memory and complicates the GUI for an undo v1.0 does not need. |
| Generic `Series` base, `Spectrum` specialises it (D-20261115-01) | Spectrum-only model | Cheap now; changing it after E4 would touch model, renderer and project file. |
| Stick lines kept as printed; summing is a display view (D-20261118-02 to -05) | Merge degenerate lines in the data; strictly ascending stick x | Rob, S013: the program's lines must be recoverable (export writes them); broadening gives the same curve either way. |
| Width-limited, anchored grouping with a fixed length on the figure | Relative tolerance (1 %); single-linkage chaining | A relative merge turns carpets of small lines into one unrealistic stick; chaining makes groups grow without bound and jump when panning. |
| Breaks as one field of `XAxis`, expanded by `render/` | Breaks as several panels in the model | The user sees one plot; arrangement and peaks must not split. Rob's "pieces glued together" idea is exactly what `render/` does. |
| Compatibility key = technique + quantity | Quantity only | IR and UV-Vis absorbance have different scales (Rob, S006). |
| Core returns `NeedsYChoice`; GUI asks | Core picks normalisation automatically | The app never guesses (CLAUDE §6.3). |
| Normalisation over cropped data | Over the visible range | Zooming must not change the values. |
| Canvas layout as nested proportional grid | Free rectangles | Covers Rob's layouts; native in Matplotlib; no overlaps to police. |
| Zoom inset holds no layers, shows the host's | Zoom inset as a copy | Rob, S006: it must update live. |
| Convertible x always accepted, even with no overlap | Treat UV-Vis + IR x as incompatible | Rob, S006: the empty stretch teaches the student. |

## 15. Points reviewed with Rob (S006)

1. **Sticks.** Theoretical sticks layers show curve and sticks by default; the user can
   hide either one, not both (§3.7).
2. **Inversion.** A panel whose first layer is IR starts with x inverted (§5). The y
   axis is never inverted by default: transmittance already shows 100 % at the top
   with bands pointing down on a normal y axis. `YAxis.inverted` stays available as
   a user option.
3. **Stack gap.** Default 1.1 (normalised) or 1.1 × largest maximum (raw): confirmed.
4. **Theoretical curve without sticks.** Kept as allowed: some tools export an already
   broadened theoretical spectrum as a plain x–y table, which the txt/csv reader loads
   as a curve and the user declares theoretical. No parser of v1.0 produces one, and
   `graphing` aims to replace those tools; the case costs nothing to keep.
