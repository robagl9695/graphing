# Test scenarios

The chains and journeys run by the integration cycle (`CLAUDE.md` §4.2). Each stage
adds its own entries; the list only grows, and an entry is removed or changed only
through a new decision. Every entry names the stage that added it and the tests that
run it.

Levels: **I** integration (public interfaces of `core/` and `render/`, no GUI),
**C** corpus harness (`tools/run_corpus.py`), **E** end to end through the real
interface (from E4).

## Integration and corpus

| ID | Stage | Level | Chain | Run by |
|---|---|---|---|---|
| S-E2-01 | E2 | I | Every registered format loads through `core.io.load`: text and spreadsheet tables (experimental curves, theoretical tables as sticks), ORCA and Turbomole outputs; declared origin used as given; supported formats listed from the registry. | `tests/integration/test_io.py` |
| S-E2-02 | E2 | C | Every corpus file is read (load → map, or parse) and compared with its sidecar; files that must fail fail with the named error; one gallery figure per file. | `tests/corpus/test_corpus.py`, `python tools/run_corpus.py` |
| S-E3-01 | E3 | I | Each theoretical corpus file that loads → layer with broadening (Gaussian FWHM 250 meV for UV-Vis, Lorentzian FWHM 4 cm⁻¹ for IR) → ε. The curve is finite and not negative. There is one stick per line above zero, and the imaginary mode is neither broadened nor drawn. | `tests/integration/test_theoretical_chain.py` |
| S-E3-02 | E3 | I | Area of the ε curve in cm⁻¹ equals K·Σ intensities within 1e-4. UV-Vis (broadened in eV) is checked on the chain itself. IR (Lorentzian) is checked on a wide grid, and the chain is checked against it point by point. | same |
| S-E3-03 | E3 | I | Scale factor and shift move the sticks to `factor·x + shift` in the broadening unit. The curve equals the broadening of the corrected lines. | same |
| S-E3-04 | E3 | I | Two transform chains: f → ε → A (b = 1 cm, c = 1e-5 mol/L) → %T and km/mol → ε → A → %T. The sticks follow the curve: scaled for the linear steps, point by point for %T. | same |
| S-E3-05 | E3 | I | The curve and the sticks are the same in cm⁻¹, nm and eV views: converting back gives x within 1e-12 and identical y. | same |
| S-E3-06 | E3 | C | Every program output that parses is broadened and converted to ε in the harness, with the same widths as S-E3-01. The gallery shows the curve with its sticks. Files that must fail to parse are not broadened. | `tests/corpus/test_corpus.py`, `python tools/run_corpus.py` |

## End to end

None yet: journeys through the interface start in E4.
