# ROUTE.md — Work plan for `graphing`

> Read on demand only. Find a task by its ID; do not load the whole file.
> Changes to this file need Rob's express authorisation (`CLAUDE.md` R3).
> Live status of each task is in `STATE.md`. The "Progress" table below is updated
> only when a stage is closed; marking a stage as done needs no authorisation.

Last revised: 2026-11-14

## How to read a task

- **Model:** H = Haiku, S = Sonnet, O = Opus, O+R = Opus proposes, stops, Rob decides.
- **Dep:** tasks that must be approved first.
- **AC:** acceptance criteria. All must pass.
- **Tests:** what must run green as evidence. "Suite" (full `pytest`, `ruff`, `mypy`)
  is implied for every task.
- `[local]` = extra check against the unpublished files in `tests/reference/`, on
  Rob's machine only. Informative; never required for a task to pass.
- Every task follows the task cycle in `CLAUDE.md` §4.1.

## Gate procedure (every stage)

A stage is approved only when: (1) all its tasks are approved; (2) its gate below
passes; (3) the **integration cycle** of `CLAUDE.md` §4.2 is green — regression,
integration tests, corpus run, end-to-end journeys, and from E15 the installed-app
smoke test. Each stage adds its own integration tests and at least one end-to-end
journey (from E4) to `docs/test-scenarios.md` and, from E4, its user-visible functions
to `docs/acceptance-checklist.md`. A version tag also needs the acceptance checklist.

## Progress (updated at stage closure)

| Stage | Content | Version at gate | Status |
|---|---|---|---|
| E0 | Foundation | 0.0.1 | done (2026-11-15) |
| E1 | Core model, units, transforms | — | not started |
| E2 | Readers and parsers | — | open: only T2.1 AC4 left (real instrument exports, `STATE.md`) |
| E3 | Theoretical spectrum engine | 0.1.0 | not started |
| E4 | GUI: single plot | 0.2.0 | not started |
| E5 | Axis interaction | — | not started |
| E6 | Peaks | 0.3.0 | not started |
| E7 | Several layers in one panel | 0.4.0 | not started |
| E8 | IR range guide | — | not started |
| E9 | Colour | 0.5.0 | not started |
| E10 | Structure | — | not started |
| E11 | Project file and export | 0.6.0 | not started |
| E12 | Double axis, subplots, inset | 0.7.0 | not started |
| E13 | Translations | 0.8.0 | not started |
| E14 | Help and manual | — | not started |
| E15 | Installers | 0.9.0 | not started |
| E16 | Validation and release | 1.0.0 | not started |

## Dependency overview

```
E0 → E1 → E2 → E3 → E4 → E5 → E7 → E12
                      ├──→ E6
                      ├──→ E8
                      ├──→ E9
                      └──→ E10
E7 → E11 ; (E4…E12) → E13 → E14 → E15 → E16
```

E6, E8, E9 and E10 are independent of each other; they are still executed one at a
time. Recommended order: E5, E6, E7, E8, E9, E11, E10, E12.

---

## E0 — Foundation

**Gate:** a fresh clone installs, lints and tests green on the three systems.

### T0.1 — Repository scaffold
- **Model:** S · **Dep:** —
- **Objective:** create the package skeleton and the git repository.
- **Deliverable:** `pyproject.toml` (src layout, package `graphing`, extras `dev`
  and `structure`), `src/graphing/{core,render,gui,translations,resources}/__init__.py`,
  `tests/{unit,gui,integration,e2e,corpus}/`, `docs/`, `tools/`, `build/`, `.gitignore`, `git init` with branch `main`.
- **AC:** (1) `pip install -e ".[dev]"` succeeds in a clean Python 3.12 environment.
  (2) `python -c "import graphing; print(graphing.__version__)"` prints `0.0.1`.
  (3) `git check-ignore` confirms `LOGBOOK.md`, `brainstorming/`, `build/` and
  `tests/reference/` are ignored. (4) `pytest` exits 0.
- **Tests:** one smoke test importing the package.

### T0.2 — Lint, format and type configuration
- **Model:** H · **Dep:** T0.1
- **Objective:** configure `ruff` and `mypy` (strict on `core/`), and `pytest`
  markers (`local_data`, `gui`, `integration`, `corpus`, `e2e`).
- **AC:** (1) `ruff check .`, `ruff format --check .`, `mypy src` exit 0.
  (2) `pytest -m local_data` skips with a readable reason when data is absent.
- **Tests:** the three commands above.

### T0.3 — Project documents
- **Model:** H · **Dep:** T0.1
- **Objective:** `LICENSE` (GPL-3.0 text), `README.md` (what it is, status, how to
  run from source), `CHANGELOG.md`, `CONTRIBUTING.md` (commit and branch rules).
- **AC:** (1) `LICENSE` is the unmodified GPL-3.0 text. (2) README states the licence
  as GPL-3.0-or-later and the development status. (3) No real person's data or
  unpublished result appears in any published file.
- **Tests:** manual check by Rob.

### T0.4 — Continuous integration
- **Model:** S · **Dep:** T0.2
- **Objective:** GitHub Actions workflow: lint, type check and tests on Windows,
  macOS and Linux, Python 3.12, Qt offscreen.
- **AC:** (1) workflow green on the three systems on `main`. (2) A deliberately
  failing test turns it red (checked on a throwaway branch).
- **Tests:** CI run links recorded in `LOGBOOK.md`.

---

## E1 — Core model, units, transforms

**Gate:** `core/` model complete and tested without any GUI import.

### T1.1 — Architecture specification
- **Model:** O+R · **Dep:** T0.1
- **Objective:** write `docs/architecture.md`: classes `Spectrum`, `Layer`, `Axis`,
  `Panel`, `Canvas`, `Project`; their fields and invariants; the inheritance rule;
  y modes; combination table; how each figure type (overlap, normalised overlap,
  stacking, double axis, subplots, inset, transformed axes; gap reserved) maps to the
  model; operations exposed to the GUI.
- **AC:** (1) every figure type listed has a worked example in terms of model
  objects. (2) the gap is representable without changing any class signature.
  (3) Rob approves the document.
- **Tests:** none (document). Review by Rob.

### T1.2 — Quantities, units and x conversions
- **Model:** S · **Dep:** T1.1
- **Objective:** `core/units.py`: x quantities wavelength (nm), wavenumber (cm⁻¹),
  energy (eV); conversions between them; constants module with sources.
- **AC:** (1) all six conversions implemented and vectorised. (2) non-positive
  input raises a named error. (3) conversion keeps x–y pairing and returns x ascending.
- **Tests:** 500 nm = 20000 cm⁻¹ = 2.479684 eV (rel. tol. 1e-6); round trip of a
  random array to rel. tol. 1e-12; error cases.

### T1.3 — Spectrum and y kinds
- **Model:** S · **Dep:** T1.2
- **Objective:** `core/spectrum.py`: immutable `Spectrum` (technique, origin, x, y,
  x unit, y kind, metadata). Y kinds: absorbance, transmittance (%), molar
  absorptivity, intensity (arbitrary), oscillator strength (sticks), IR intensity
  (km/mol, sticks).
- **AC:** (1) construction validates lengths and finiteness; curves need strictly
  ascending x; sticks keep every line in file order, repeated positions allowed
  (D-20261118-02). (2) raw
  arrays cannot be mutated from outside. (3) sticks and curves are distinct types.
- **Tests:** validation errors; immutability; equality.

### T1.4 — Y transforms
- **Model:** S · **Dep:** T1.3
- **Objective:** `core/transforms.py`: normalise (to maximum; to the value at a
  chosen x), constant levelling, transmittance↔absorbance
  (A = 2 − log₁₀ %T), log₁₀, inverse. Each transform is a parameter object applied
  on demand.
- **AC:** (1) normalise-to-max gives max exactly 1. (2) T↔A round trip to 1e-12.
  (3) %T ≤ 0 and log of non-positive values produce a named error, never NaN silently.
  (4) transforms compose in a declared order and are reversible by removing them.
- **Tests:** one per transform plus composition and error cases.

### T1.5 — Region operations
- **Model:** S · **Dep:** T1.3
- **Objective:** select an x interval; crop in x; view limits in x and y.
- **AC:** (1) crop returns a new spectrum, raw data intact. (2) interval given in
  any x unit. (3) empty selection raises a named error.
- **Tests:** crop bounds inclusive; unit-independent result; error case.

### T1.6 — Canvas, panel and layer model
- **Model:** O · **Dep:** T1.1, T1.4, T1.5
- **Objective:** implement the model of `docs/architecture.md`.
- **AC:** (1) first layer fixes panel axes; later layers are converted. (2) changing
  an axis quantity updates every layer. (3) y modes overlap / normalised / stacked
  give the documented y values. (4) pasted layer is an independent copy.
  (5) forbidden combinations raise a named error. (6) no import from `render/` or `gui/`.
- **Tests:** one test per AC; an import-graph test enforcing the layer rule of
  `CLAUDE.md` §6.2.

---

## E2 — Readers and parsers

**Gate:** every v1.0 input format loads into a `Spectrum` through one interface.

### T2.1 — Delimited text reader (txt, csv)
- **Model:** S · **Dep:** T1.3
- **Objective:** `core/readers/text.py`: detect encoding, delimiter (comma,
  semicolon, tab, spaces), decimal separator (point or comma), preamble and header
  rows; return a table plus the detected settings, all overridable.
- **AC:** (1) the 16 fixture combinations (4 delimiters × 2 decimal separators ×
  with/without preamble) load to identical numeric tables. (2) ambiguous case
  (comma as both delimiter and decimal) is reported, not guessed. (3) a file with no
  numeric block raises a named error. (4) every instrument export in the corpus loads
  to the values in its sidecar (blocked until the files arrive; see `STATE.md`).
- **Tests:** parametrised fixture matrix; error cases.

### T2.2 — Spreadsheet readers (xlsx, ods)
- **Model:** S · **Dep:** T2.1
- **Objective:** `core/readers/sheet.py`: same table abstraction; sheet selection.
- **AC:** (1) the same data saved as xlsx and ods equals the csv result. (2) merged
  header cells and empty leading rows are handled. (3) formulas are read by value.
- **Tests:** fixtures generated by script; equality with T2.1 result.

### T2.3 — Column mapping
- **Model:** S · **Dep:** T2.2
- **Objective:** `core/readers/mapping.py`: from a table plus user choices (x
  column, one or more y columns, x unit, y kind) build one `Spectrum` per y column;
  suggest a default mapping.
- **AC:** (1) n y-columns give n spectra sharing x. (2) non-numeric cells in a
  chosen column are reported with row numbers. (3) the suggestion is never applied
  without the caller confirming.
- **Tests:** multi-column fixture; error reporting.

### T2.4 — Test corpus and harness
- **Model:** S · **Dep:** T0.2 · **Needs:** corpus files from Rob (see `STATE.md`)
- **Objective:** `tests/corpus/` layout, sidecar schema (program or instrument,
  version, molecule, producer, expected result), and `tools/run_corpus.py`: runs
  every corpus file through load → process → plot → export and writes a gallery of
  figures to `build/corpus-gallery/`. Small synthetic files for edge cases (imaginary
  mode, malformed number, empty block), written by script.
- **AC:** (1) the harness discovers files from their sidecars; adding a file needs no
  code change. (2) a file whose result differs from its sidecar fails the run and is
  named. (3) the gallery has one figure per file. (4) stages that are not built yet
  are skipped cleanly, so the harness is usable from E2 and grows with each stage.
  (5) every corpus file has Rob's confirmation that it can be published.
- **Tests:** harness run on the initial corpus; a deliberately wrong sidecar fails.

### T2.5 — ORCA parsers
- **Model:** S · **Dep:** T2.4, T1.3
- **Objective:** `core/parsers/orca.py`: absorption spectrum via transition
  electric dipole moments (4.x, 6.x); IR spectrum block (6.x). Port from
  `qclab-utilities/common/parsers`.
- **AC:** (1) every ORCA file in the corpus parses to the values in its sidecar
  (state or mode count, first and last rows). (2) the velocity and CD blocks are not
  picked up. (3) an output without the block raises a named error that names the
  missing block. (4) supported version families are exactly those present in the corpus.
- **Tests:** corpus tests; synthetic edge cases; `[local]` checks from `case.json`.

### T2.6 — Turbomole parsers
- **Model:** S · **Dep:** T2.4, T1.3
- **Objective:** `core/parsers/turbomole.py`: `exspectrum`, `escf.out`, `vibspectrum`.
- **AC:** as T2.5 for the Turbomole files in the corpus; imaginary modes are returned
  flagged, not dropped.
- **Tests:** corpus tests; the imaginary-mode synthetic case; `[local]` `crq200` checks.

### T2.7 — Single loading interface
- **Model:** S · **Dep:** T2.3, T2.5, T2.6
- **Objective:** `core/io.py`: one entry point taking (path, technique, origin,
  options) and dispatching. Format is chosen from the user's declaration, not guessed
  from content beyond the file type.
- **AC:** (1) every format loads through it. (2) declaring a wrong origin does not
  raise or warn; the data is read as declared. (3) list of supported formats is
  generated from the registered readers. (4) stick spectra keep every line as printed,
  in file order, each with its label (mode or state number).
- **Tests:** one integration test per format in `tests/integration/`; first full
  corpus run.

---

## E3 — Theoretical spectrum engine

**Gate (0.1.0):** sticks from any parser become a physically correct curve.

### T3.1 — Line shapes
- **Model:** S · **Dep:** T1.2
- **Objective:** `core/lineshapes.py`: Gaussian, Lorentzian, Voigt, parametrised by
  FWHM, area-normalised.
- **AC:** (1) numerical area = 1 within 1e-6 on a wide grid. (2) measured FWHM
  equals the parameter within the grid step. (3) Voigt tends to Gaussian and to
  Lorentzian in the two limits.
- **Tests:** one per AC for each shape.

### T3.2 — Broadening
- **Model:** O · **Dep:** T3.1, T2.5, T2.6
- **Objective:** `core/broadening.py`: sticks → curve. Broadening is done in an
  energy-linear variable (cm⁻¹ or eV), then converted for display. The broadened
  curve keeps the y quantity of the sticks (oscillator strength or km/mol)
  (D-07); conversions to other quantities are T3.4. Grid chosen from the FWHM.
- **AC:** (1) the integral of the broadened curve of one stick reproduces its height
  within 1e-4 relative. (2) the curve is computed once, in the broadening unit;
  changing the display unit converts each x value and keeps its y value, so converting
  the displayed x back to the broadening unit recovers the same points (x within 1e-12
  relative, y identical) (D-20261122-02). (3) two lines at the same position broaden to the same curve as one line
  of the summed height (1e-12 relative); the curve does not depend on the view.
- **Tests:** single-stick integrals; unit invariance.

### T3.3 — Scale factor and shift of theoretical positions (D-20261122-07)
- **Model:** S · **Dep:** T3.2
- **Objective:** two optional corrections of theoretical line positions, both stored
  as `Broadening` parameters and valid for IR and UV-Vis: a multiplicative scale
  factor (default 1.0) and an additive shift (default 0.0), `x' = factor·x + shift`,
  in the broadening unit (cm⁻¹ or eV; UV-Vis sticks in nm are converted first). The
  IR scale factor is standard practice; for UV-Vis both are user calibrations
  against experiment, with no universal value. Lines whose corrected position is not
  above zero are neither broadened nor drawn, as for imaginary modes.
- **AC:** (1) factor 1.0 and shift 0.0 are a no-op to machine precision. (2) factor
  and shift are applied to stick positions before broadening, and the drawn sticks
  follow the curve. (3) non-positive or non-finite factor, and non-finite shift,
  raise a named error. (4) lines at or below zero before the correction are not
  moved by the shift.
- **Tests:** one per AC.

### T3.4 — Absorptivity and Beer–Lambert conversions
- **Model:** O · **Dep:** T3.2, T1.4
- **Objective:** optional y transforms the user chooses (D-07): oscillator strength
  → molar absorptivity; km/mol → molar absorptivity (D-20261117-01); molar
  absorptivity → absorbance by Beer–Lambert, asking path length b and
  concentration c; experimental absorbance → molar absorptivity, asking b and c.
  Absorbance → %T uses the existing transform. No direct km/mol → A or %T.
  Constants taken from `qclab-utilities` and re-derived in the docstring with their
  source.
- **AC:** (1) integrated absorptivity of one stick reproduces its oscillator
  strength (UV-Vis) or intensity (IR) within 1e-4 relative. (2) A → ε → A with the
  same b and c is the identity within 1e-12 relative; non-positive b or c raises a
  named error. (3) curves for the corpus files agree within 1e-6 relative with
  `irspectra` output, and with `absspectra` output multiplied by
  K_CODATA / 2.315115e8 (qclab's f → ε constant differs from the CODATA 2018 value
  by 1.02e-4; D-20261122-09). (4) derivation of the conversion constants is written
  in `docs/theory.md`.
- **Tests:** one per AC; comparison on the corpus.

---

## E4 — GUI: single plot

**Gate (0.2.0):** a user can load any supported file and see it plotted, in a
frozen-free run from source on Windows and Linux.

### T4.1 — Interface specification
- **Model:** O+R · **Dep:** T1.1
- **Objective:** `docs/ui-spec.md`: main window layout (task bar, canvas list,
  plot area, side panel), import flow screen by screen, where each tool lives,
  keyboard and mouse actions, wireframes. Also creates `docs/acceptance-checklist.md`
  (in Spanish, `CLAUDE.md` R7 and §4.2) with the items of the import flow.
- **AC:** (1) every v1.0 function in `CLAUDE.md` §6.4 has a place in the interface.
  (2) the import flow takes at most three screens. (3) Rob approves.
- **Tests:** none (document).

### T4.2 — Renderer
- **Model:** O · **Dep:** T1.6
- **Objective:** `render/`: model → Matplotlib figure for one panel. Conventions:
  wavenumber axis decreasing to the right for IR; EQ palette; sticks drawn as
  vertical lines when requested; sticks summed for display by
  `core.sticks.group_sticks`: same printed position always; unresolved lines within
  the display tolerance (≈0.5 mm on the figure) unless "sum sticks" is off;
  recomputed when the view changes; a summed stick has its tip in a lighter tone of
  the layer colour (D-20261118-03, -04, -05). Default x view of a stick layer: the
  outermost lines ± 5 FWHM, with the FWHM taken in the displayed unit (in nm,
  Δλ = hc/(E − ΔE/2) − hc/(E + ΔE/2); if ΔE/2 ≥ E, half the energy of that line)
  (D-20261122-01).
- **AC:** (1) rendering is a pure function of the model (same model, same figure).
  (2) no Qt import. (3) image-comparison tests pass for curve, sticks, curve+sticks,
  IR transmittance, a degenerate pair, and an unresolved pair at two zoom levels.
- **Tests:** `pytest-mpl`-style image comparisons with tolerance; purity test.

### T4.3 — Application shell
- **Model:** S · **Dep:** T4.1, T4.2
- **Objective:** `gui/`: main window, menus, task bar, canvas list, embedded plot,
  settings storage, translation hooks on every string.
- **AC:** (1) app starts and closes cleanly offscreen. (2) no user-visible string
  outside the translation wrapper (checked by a test that scans the source).
  (3) creating, renaming, selecting and deleting a canvas works.
- **Tests:** `pytest-qt` for each action; string-scan test.

### T4.4 — Help infrastructure
- **Model:** S · **Dep:** T4.3
- **Objective:** registry of help entries keyed by parameter ID; "?" button widget
  that shows the entry; loader for the three languages.
- **AC:** (1) a parameter widget registered without a help ID fails a test.
  (2) missing text in any language fails a test. (3) the "?" opens the right entry.
- **Tests:** completeness test; `pytest-qt` click test.

### T4.5 — Import dialog
- **Model:** S · **Dep:** T4.3, T2.7
- **Objective:** file (dialog or drag and drop) → technique → origin → table preview
  with X and Y check boxes, decimal separator, units → plot.
- **AC:** (1) each v1.0 format reaches a plot. (2) the preview shows the table as
  read and updates when the decimal separator or delimiter is changed. (3) cancelling
  at any step leaves the project unchanged. (4) reader errors are shown in plain
  language, translated.
- **Tests:** `pytest-qt` flows for txt, xlsx, ORCA, Turbomole; cancel test.

### T4.6 — Theoretical parameters panel
- **Model:** S · **Dep:** T4.5, T4.4, T3.3
- **Objective:** line shape, FWHM (with unit), scale factor, shift (in cm⁻¹ or eV,
  as set by T3.3), show sticks; the "sum sticks" control (it turns off only the summing of unresolved lines), with its
  "?" entry; the plot updates live.
- **AC:** (1) each control changes the model parameter and re-renders. (2) each
  control has its "?" entry. (3) invalid values are refused with a message.
- **Tests:** `pytest-qt` per control; help completeness.

---

## E5 — Axis interaction

**Gate:** all single-spectrum view operations work from the plot itself.

### T5.1 — Clickable axis titles
- **Model:** S · **Dep:** T4.6
- **Objective:** click on the x title → choose nm, cm⁻¹ or eV; click on the y title
  → normalisation, T↔A, log, inverse, levelling.
- **AC:** (1) each choice maps to the `core/` operation and re-renders. (2) axis
  labels and units update, translated. (3) choices that are invalid for the data are
  disabled with a reason.
- **Tests:** `pytest-qt` per choice.

### T5.2 — Zoom, pan, crop, region selection
- **Model:** S · **Dep:** T5.1
- **Objective:** zoom in and out, pan, select a region by dragging or by typing
  limits, crop to it in x and in y, reset view.
- **AC:** (1) typed limits accept the current axis unit. (2) crop is undoable.
  (3) reset returns to the full data range.
- **Tests:** `pytest-qt` with simulated drags; undo test.

---

## E6 — Peaks

**Gate (0.3.0):** peaks can be found, added, removed and labelled legibly.

### T6.1 — Peak detection
- **Model:** O · **Dep:** T1.4
- **Objective:** `core/peaks.py`: automatic detection with an intensity threshold;
  categories all / major peaks / shoulders; works for maxima (absorbance) and minima
  (transmittance). Port and modernise `qclab-utilities/common/peaks.py`.
- **AC:** (1) on synthetic sums of known bands, every band above the threshold is
  found within one grid step and none is invented. (2) a shoulder next to a much
  sharper peak is found (regression case from `qclab-utilities`). (3) noise at 1 %
  of the maximum produces no spurious peak at the default threshold.
- **Tests:** synthetic cases with known answers; noise case.

### T6.2 — Manual picking
- **Model:** S · **Dep:** T6.1, T5.2
- **Objective:** crosshair cursor (vertical and horizontal lines) with readout;
  click to add a peak (snap to the local extremum, optional); click to remove.
- **AC:** (1) readout shows x and y in the current units. (2) add and remove are
  undoable. (3) manual and automatic peaks coexist and are distinguishable.
  (4) clicking a summed stick shows "sum of g degenerate lines" or "n lines not
  resolved at this zoom", with the range and the members.
- **Tests:** `pytest-qt` click tests.

### T6.3 — Label thinning
- **Model:** O · **Dep:** T6.2
- **Objective:** place peak labels without overlap, using label size in pixels at
  the current zoom; when crowded, keep the most prominent and thin the rest.
- **AC:** (1) no two labels overlap at any zoom level in the test set. (2) the most
  prominent peak in any crowded group is always labelled. (3) thinning is recomputed
  on zoom and resize.
- **Tests:** geometric overlap test on rendered label boxes; image comparison.

---

## E7 — Several layers in one panel

**Gate (0.4.0):** theory and experiment can be compared in one plot three ways.

### T7.1 — Copy and paste between canvases
- **Model:** S · **Dep:** T5.2
- **Objective:** copy a plot; paste onto an existing plot → new layer in that panel.
- **AC:** (1) pasted layer is converted to the target axes. (2) editing it does not
  change the source canvas. (3) undoable.
- **Tests:** `pytest-qt` flow; independence test.

### T7.2 — Y modes
- **Model:** S · **Dep:** T7.1
- **Objective:** switch a panel between overlap, normalised overlap and stacking;
  stacking offset adjustable.
- **AC:** (1) each mode renders the `core/` values. (2) the y axis label states the
  mode. (3) switching modes loses no data.
- **Tests:** `pytest-qt` per mode; image comparisons.

### T7.3 — Layer management and legend
- **Model:** S · **Dep:** T7.1
- **Objective:** layer list: rename, colour, line style, order, show/hide, delete;
  legend on the plot.
- **AC:** (1) each action updates plot and legend. (2) deleting the first layer
  keeps the panel axes as they were.
- **Tests:** `pytest-qt` per action.

---

## E8 — IR range guide

**Gate:** the guide can be shown over any IR plot, filtered by element or bond.

### T8.1 — Guide data
- **Model:** H (transcription) + Rob (review) · **Dep:** open decision D-05
- **Objective:** `resources/ir_guide.json`: one entry per bond or group — label,
  elements involved, wavenumber range, usual intensity, note, citation(s). First
  compilation from Wade (Appendix 2B), Vogel and Nakamoto; own layout and wording.
- **AC:** (1) every entry has at least one citation with page. (2) the file
  validates against a schema. (3) no table or figure is reproduced from a source.
  (4) Rob signs off every entry.
- **Tests:** schema validation; range sanity (low < high, within 400–4000 cm⁻¹).

### T8.2 — Guide overlay
- **Model:** S · **Dep:** T8.1, T5.2
- **Objective:** dialog to choose elements or bonds; horizontal range bars drawn
  over the plot with labels; toggle on and off.
- **AC:** (1) choosing elements shows exactly the entries that involve only those
  elements. (2) bars follow the x axis unit and direction. (3) the wording is
  orientative (`CLAUDE.md` §11). (4) the overlay is offered only for IR.
- **Tests:** filter logic unit test; `pytest-qt` flow; image comparison.

---

## E9 — Colour

**Gate (0.5.0):** a UV-Vis spectrum gives XYZ, RGB and hex, as a function of
concentration.

### T9.1 — Colour engine
- **Model:** O · **Dep:** T1.4
- **Objective:** `core/colour.py`: port `cie.py`, `srgb.py` and `colorcoords/core.py`.
  Absorption spectrum + concentration + path length → transmitted light under a
  standard illuminant → CIE XYZ → xy, sRGB, hex. Review each restriction of the
  original script and keep, remove or document it.
- **AC:** (1) zero absorbance returns the illuminant white point. (2) the four
  synthetic dyes reproduce `colorcoords` output within 1e-6. (3) out-of-gamut colours
  are flagged, not clipped silently. (4) spectra not covering 380–780 nm are refused
  with a message saying which range is missing. (5) every restriction of the original
  script is listed in `docs/theory.md` with its justification.
- **Tests:** one per AC.

### T9.2 — Colour panel
- **Model:** S · **Dep:** T9.1, T4.6
- **Objective:** swatch, XYZ, RGB and hex values, concentration and path-length
  controls, copy to clipboard; offered only for UV-Vis.
- **AC:** (1) values equal the engine's. (2) swatch updates live with concentration.
  (3) every control has its "?" entry.
- **Tests:** `pytest-qt`; help completeness.

---

## E10 — Structure

**Gate:** a 2D structure can be placed on a canvas.

### T10.1 — Image annotation
- **Model:** S · **Dep:** T5.2
- **Objective:** "Add structure": paste or load an image (PNG, SVG, JPEG) drawn in
  another program; move and resize it on the canvas.
- **AC:** (1) the image is stored in the project. (2) it is exported with the figure.
- **Tests:** `pytest-qt`; export check.

### T10.2 — Structure from SMILES
- **Model:** S · **Dep:** T10.1
- **Objective:** type a SMILES string → 2D depiction with RDKit, wedges included.
  RDKit is an optional dependency.
- **AC:** (1) valid SMILES gives an image; invalid SMILES gives a plain-language
  error. (2) without RDKit installed the option is disabled with an explanation and
  the app works otherwise.
- **Tests:** with and without RDKit (CI job for each).

---

## E11 — Project file and export

**Gate (0.6.0):** work survives closing the app and leaves it as figure or data.

### T11.1 — Project file format
- **Model:** O+R (format) then S (implementation) · **Dep:** T7.3
- **Objective:** versioned project file (zip with JSON + raw data); save, open,
  schema version and migration hook.
- **AC:** (1) save → open reproduces an equal model. (2) a file with a newer schema
  version is refused with a clear message. (3) raw data is stored, never only the
  transformed data. (4) Rob approves the format before implementation.
- **Tests:** round-trip equality on a project using every v1.0 feature built so far.

### T11.2 — Figure export
- **Model:** S · **Dep:** T4.2
- **Objective:** export the canvas to PNG, SVG and PDF with size and resolution.
- **AC:** (1) the three formats open in standard viewers. (2) fonts are embedded in
  PDF and SVG. (3) exported size equals the requested size.
- **Tests:** file-type and dimension checks.

### T11.3 — Data export
- **Model:** S · **Dep:** T6.1, T3.2
- **Objective:** export processed spectra, the stick lines of theoretical layers and
  the peak table to CSV, with a header recording the transforms and parameters applied.
- **AC:** (1) exported CSV reloads through T2.1 to the same numbers. (2) the header
  lists every applied transform. (3) stick export writes every original line in file
  order with its label, its printed position and its position after the scale
  factor; never the summed sticks.
- **Tests:** export → reload equality.

---

## E12 — Double axis, subplots, inset

**Gate (0.7.0):** the multi-panel figure types work without changing E1–E11 interfaces.

### T12.1 — Second y axis
- **Model:** S · **Dep:** T7.2
- **Objective:** assign a layer to a right-hand y axis with its own quantity and
  transform.
- **AC:** (1) each axis keeps its own scale and label. (2) `stacked` mode is
  disabled while a second axis exists, with a reason. (3) peaks and guide follow the
  axis of their layer.
- **Tests:** `pytest-qt`; image comparison.

### T12.2 — Subplots
- **Model:** O · **Dep:** T7.1
- **Objective:** paste on empty canvas space → new panel beside; grid layouts with
  adjustable proportions; optional shared x.
- **AC:** (1) layouts 1×2, 2×1, 2×2 and unequal proportions render correctly.
  (2) each panel keeps full single-panel behaviour. (3) shared x links zoom and units.
- **Tests:** `pytest-qt`; image comparisons per layout.

### T12.3 — Inset
- **Model:** S · **Dep:** T12.2
- **Objective:** inset panel inside a panel: free content, or linked zoom of a
  selected region with the region marked on the parent.
- **AC:** (1) linked inset follows the selected region. (2) an inset cannot receive
  an inset. (3) inset is movable and resizable.
- **Tests:** `pytest-qt`; image comparison.

---

## E13 — Translations

**Gate (0.8.0):** the interface is complete in Spanish, English and Portuguese.

### T13.1 — Translation round trip
- **Model:** S · **Dep:** T4.3
- **Objective:** scripts: source strings → Qt translation files → spreadsheet
  (`context | English | Español | Português`) and back.
- **AC:** (1) round trip loses nothing. (2) new or changed strings are flagged in
  the sheet. (3) the sheet opens in Excel and LibreOffice.
- **Tests:** round-trip test on a sample catalogue.

### T13.2 — Spanish translation
- **Model:** O (draft) + Rob (review) · **Dep:** T13.1, E12
- **AC:** (1) no empty Spanish cell. (2) Rob approves.
- **Tests:** completeness test.

### T13.3 — Portuguese translation
- **Model:** O (optional draft) + collaborator (translation/review) · **Dep:** T13.1, E12
- **AC:** (1) no empty Portuguese cell. (2) the collaborator approves.
- **Tests:** completeness test.

### T13.4 — Language switching
- **Model:** S · **Dep:** T13.2
- **Objective:** language chosen at first start and in settings; switch without
  restarting.
- **AC:** (1) every visible string changes on switch. (2) number formatting follows
  the language but files are always read as declared in the import dialog.
- **Tests:** `pytest-qt` switch test scanning all widgets.

---

## E14 — Help and manual

**Gate:** every parameter is explained; a new user can follow the manual start to finish.

### T14.1 — Help texts
- **Model:** O + Rob · **Dep:** T13.4
- **Objective:** the "?" entries: what the parameter is, what changing it does,
  a sensible value. Spanish first, then English and Portuguese.
- **AC:** (1) help completeness test passes for the three languages. (2) no entry
  assumes prior knowledge of spectroscopy software. (3) Rob approves the Spanish.
- **Tests:** completeness test.

### T14.2 — Manual
- **Model:** O + Rob · **Dep:** T14.1
- **Objective:** LaTeX manual: installation (including the unsigned-installer
  warnings), quick start, each tool with a worked example, theory summary, sources of
  the IR guide, troubleshooting. Spanish, then English and Portuguese.
- **AC:** (1) builds to PDF without warnings in the three languages. (2) every
  figure is generated by the app from public data. (3) Rob approves the Spanish.
- **Tests:** build in CI.

---

## E15 — Installers

**Gate (0.9.0):** a person with no Python installs and runs the app on each system.

### T15.1 — Frozen build
- **Model:** O · **Dep:** E12
- **Objective:** PyInstaller configuration; frozen app starts and passes a smoke
  script (load a fixture, plot, export) on the three systems in CI.
- **AC:** (1) smoke script passes on the three systems. (2) translations, help, IR
  guide and icons are found by the frozen app. (3) size is recorded.
- **Tests:** CI smoke job.

### T15.2 — Installers
- **Model:** O · **Dep:** T15.1
- **Objective:** Windows installer, macOS disk image, Linux AppImage; language
  choice at install where the system allows.
- **AC:** (1) install, start, uninstall work on a clean machine of each system.
  (2) file association for the project file works.
- **Tests:** acceptance checklist per system (T15.4).

### T15.3 — Release workflow
- **Model:** S · **Dep:** T15.2
- **Objective:** a version tag builds the three installers and attaches them, with
  checksums, to a GitHub release.
- **AC:** (1) a test tag produces the three artefacts. (2) checksums are published.
- **Tests:** dry run on a pre-release tag.

### T15.4 — Tests on real machines
- **Model:** Rob (Windows, Linux, borrowed macOS) · **Dep:** T15.2
- **AC:** the acceptance checklist passes on the three systems; results logged.

---

## E16 — Validation and release

**Gate (1.0.0):** validation report approved by Rob; name and legal questions closed.

### T16.1 — Numerical validation report
- **Model:** O · **Dep:** E12
- **Objective:** `docs/validation.md`: broadening against `absspectra`/`irspectra`;
  unit conversions; peak positions; IR guide against spectra from SDBS and NIST.
- **AC:** every comparison states data source, tolerance and result. Rob approves.

### T16.2 — Experimental validation of colour
- **Model:** Rob and lab (measurements) + O (analysis) · **Dep:** T9.1
- **Objective:** UV-Vis spectra, dilution series and photographs of coloured
  compounds (lawsone derivatives); compare computed and observed colour.
- **AC:** report with the agreement found and the limits of validity. Rob approves.

### T16.3 — Public example data
- **Model:** S (search) + Rob · **Dep:** —
- **Objective:** choose, from the corpus and from published datasets (with their
  paper), the examples shipped with the app and used in the manual.
- **AC:** each dataset has a citation and a licence that allows redistribution.

### T16.4 — Release 1.0.0
- **Model:** S · **Dep:** all, including T16.6
- **AC:** open decision D-01 closed and D-02 reviewed (D-20261114-11); CHANGELOG complete; installers
  published; manual in three languages attached.

### T16.5 — Acceptance run
- **Model:** Rob and group (testing) + O (support) · **Dep:** E15
- **Objective:** go through `docs/acceptance-checklist.md` in full, as users, on the
  installed app.
- **AC:** (1) every item passes on Windows, macOS and Linux. (2) results are logged.
  (3) every failure is recorded as a defect, fixed on a `fix/` branch, and the run is
  repeated.
- **Tests:** the checklist itself.

### T16.6 — Beta
- **Model:** Rob and testers + O (triage) · **Dep:** T16.5, D-08
- **Objective:** tag `1.0.0-beta.N`, give the installers to a small group chosen by
  Rob, collect their bug reports, fix them on `fix/` branches, and release a new
  `beta.N` when needed.
- **AC:** (1) the test period set by Rob ends with no open blocking defect.
  (2) reports and fixes are logged.
- **Tests:** the testers' use; regression and acceptance items of every fix.

---

## Backlog (v1.1 and later)

| ID | Item |
|---|---|
| B-01 | Axis gap (model already reserves it) |
| B-02 | Plot digitizer |
| B-03 | Gaussian parser (needs real outputs) |
| B-04 | MOPAC parser (needs real outputs) |
| B-05 | Code signing for Windows and macOS installers |
| B-06 | Further techniques and plot types (e.g. density of states) |
