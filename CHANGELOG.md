# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- E3 integration tests: every theoretical corpus file, and the ORCA IR and Turbomole
  escf layouts, go through load → broadening → ε → A → %T, with area, position
  correction and view checks. The corpus harness broadens program outputs to ε and the
  gallery shows each curve with its sticks. `docs/test-scenarios.md` lists the
  integration chains. (E3)
- Conversions to molar absorptivity: f → ε (constant from CODATA 2018) and km/mol → ε
  for broadened theoretical layers, and Beer–Lambert ε ↔ A with path length (cm) and
  concentration (mol/L). On an ε axis a stick shows the maximum of its band alone.
  Derivations in `docs/theory.md`. (T3.4)
- Scale factor and shift of theoretical line positions, `x' = factor·x + shift` in cm⁻¹ or eV,
  for IR and UV-Vis, applied before broadening; the drawn sticks follow. (T3.3)
- Architecture specification (`docs/architecture.md`) and glossary of terms
  (`docs/glossary.md`). (T1.1)
- X quantities (wavelength, wavenumber, energy), conversions between them,
  physical constants module and named errors `NonPositiveValue` and
  `IncompatibleXQuantity`. (T1.2)
- Immutable `CurveData` and `StickData`, `Series` and `Spectrum` with declared
  technique and origin, y quantities and units, and errors `InvalidData` and
  `InvalidUnit`. (T1.3)
- Y transforms (levelling, normalisation to maximum or at an x, %T and absorbance,
  log10, inverse) and their ordered composition, with named errors. (T1.4)
- `Interval` in any x unit, inclusive `crop` of curves, sticks and spectra, and view-limit
  validation, with errors `InvalidInterval` and `EmptySelection`. (T1.5)
- Figure model (`core/model/`): project, canvas and proportional grid, panel, x and y
  axes, layer arrangement, layers, style, broadening parameters and insets; the
  operations the GUI will call (`core/operations.py`), with inheritance of axes from
  the first layer, the y-compatibility choice (normalise or double y axis) and atomic
  failure; the evaluation pipeline for curves (`core/evaluate.py`); named errors for
  every forbidden combination. Stick layers are evaluated from E3. (T1.6)
- Delimited text reader (`core/readers/text.py`): detects encoding, delimiter, decimal
  separator, preamble and header, with overrides; errors `NoNumericBlock`,
  `AmbiguousFormat` and `UnreadableFile`. (T2.1)
- Spreadsheet reader (`core/readers/sheet.py`): xlsx and ods into the same table as text
  files, with sheet selection, merged header cells and formulas read by stored value. (T2.2)
- Column mapping (`core/readers/mapping.py`): one spectrum per chosen y column from a read
  table, a header-based suggestion that is never applied without confirmation, and errors
  `InvalidMapping` and `NonNumericCells`. (T2.3)
- Public test corpus (`tests/corpus/`) with sidecars, a real IR export, synthetic files
  (`tools/make_synthetic.py`) and the harness `tools/run_corpus.py`, which checks every file
  against its sidecar and writes a gallery of figures. (T2.4)
- ORCA parsers (`core/parsers/orca.py`): absorption block via transition electric dipole
  moments (4.x and 6.x layouts; velocity and CD blocks ignored) and the 6.x `IR SPECTRUM` block,
  with errors `MissingBlock` and `MalformedBlock`. Support is not claimed until a real file is in
  the corpus. (T2.5)
- Turbomole parsers (`core/parsers/turbomole.py`): `exspectrum`, the per-state paragraphs of
  `escf.out` and `vibspectrum`. The IR reader returns every mode with `ir_active`, `raman_active`
  and `imaginary` flags and drops nothing. Support is not claimed until a real file is in the
  corpus. (T2.6)
- `core.broadening`: sticks → curve in cm⁻¹ or eV on an automatic grid (step FWHM/50,
  range ± 5 FWHM); stick layers are now evaluated, curve and sticks together, and the
  sticks follow the curve through crop, x conversion, y transforms and arrangement.
  `Broadening` gains `fwhm_lorentzian` (Voigt) and accepts a FWHM only in cm⁻¹ or eV.
  (T3.2)

### Fixed

- A missing or non-numeric cell inside a table of numbers (`0.5x`, `OVRFLW`, `N/A`, an empty
  cell) made the text and spreadsheet readers silently return a shorter table; they now raise
  `MalformedCell` naming the line or row. (X-01, X-02)
- `StickData` keeps every line as the program printed it (any order, repeated positions) and
  gains optional per-line `labels`; new `Style.sum_sticks` and `core.sticks.group_sticks` for
  summing degenerate and unresolved lines for display. (X-03)
- `core.io.load`: one entry point for text and spreadsheet tables and for ORCA and Turbomole
  outputs, driven by the declared technique and origin; `supported_formats()` lists the
  registered formats. (T2.7)
- `core.lineshapes`: unit-area Gaussian, Lorentzian and Voigt profiles by FWHM, and the
  approximate Voigt FWHM. (T3.1)
- Test fixtures and the artificial Turbomole corpus files (`artificial`, `broken-row`,
  `no-header` `.exspectrum`) used values copied from unpublished program outputs; they
  now use synthetic values only, and the local-data tests read their expected values
  from a file kept with the unpublished outputs. (X-04)

## [0.0.1] - 2026-11-15

### Added

- Repository scaffold: package layout, `pyproject.toml`, test folders and
  governance files (`CLAUDE.md`, `ROUTE.md`, `STATE.md`). (T0.1)
- Lint, format and type configuration: `ruff` and `mypy` (strict on `graphing.core`),
  pytest markers, and skipping of `local_data` tests when their data is absent. (T0.2)
- Project documents: `LICENSE` (GPL-3.0), `README.md`, `CHANGELOG.md` and
  `CONTRIBUTING.md`. (T0.3)
- Continuous integration: GitHub Actions workflow running ruff, mypy and pytest on
  Linux, Windows and macOS with Python 3.12. (T0.4)
