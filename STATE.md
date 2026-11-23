# STATE.md — Current state of `graphing`

> Read at the start of every session, after `CLAUDE.md`. Maintained without prior
> approval; every change is reported.

Last updated: 2026-11-22 · Session S019

## Next action

**Close E3 (gate 0.1.0): waiting for Rob.** The E3 integration cycle is green (S019): 486 passed, 2 skipped; corpus 33/33, the 5 program outputs broadened to ε; `tests/integration/test_theoretical_chain.py`; `docs/test-scenarios.md`. Rob decides:
(1) close E3 and mark E1 done (verified);
(2) E2 stays open; it depends only on T2.1 AC4 (real instrument exports from Kenneth); marked so in `ROUTE.md` (Rob, S019);
(3) the 0.1.0 bump, the CHANGELOG release and the tag `v0.1.0`;
(4) the push and a CI run: done (S019); `main` pushed at `a047ff4`, CI run 45087873338 green on Ubuntu, macOS and Windows;
(5) X-04 fixed (S019, see known defects).
Then T4.1.

Note: `ROUTE.md` T4.6 now lists the shift (authorised by Rob, S017); its "?" help must
cover shift and scale factor. The manual must say that scale factor and
shift act in energy (cm⁻¹ or eV), so in a nm view a constant shift is not constant in nm.

Acceptance checklist and beta wired into `CLAUDE.md` and `ROUTE.md` (S008, R3): the
checklist (`docs/acceptance-checklist.md`, Spanish) is created in T4.1 and grows with
every user-visible task; full run T16.5 before the beta T16.6.

## Work priority

1. E0 → E3: foundation and tested core, no GUI.
2. E4 → E7: everything a user does in a **single plot**. This is the centre of the app.
3. E8, E9, E11, E10: IR guide, colour, project file and export, structure.
4. E12: double axis, subplots, inset.
5. E13 → E16: translations, help and manual, installers, validation, release.

## Tasks in progress

None.

## Tasks done

T0.1 Repository scaffold (S002, commits `049f7a7`, `197ef27`). All AC verified on Python 3.12.10.
T0.2 Lint, format and type configuration (S003, commit `557b251`). All AC verified on Python
3.12.10: ruff, format, mypy clean; `local_data` skips with a reason when `tests/reference/` is
absent.
T0.3 Project documents (S003, commit `7c79e7e`). `LICENSE` verified against the official GPL-3.0
hash; README, CHANGELOG and CONTRIBUTING reviewed by Rob and merged.
T0.4 Continuous integration (S004, PR #1, merged as `2fe60e4`). AC1: CI green on ubuntu,
windows and macos on the PR and on `main`. AC2: deliberate failure on PR #2 turned all three
red; PR closed unmerged, branch deleted. Runs: see `LOGBOOK.md`.
T1.1 Architecture specification (S006). `docs/architecture.md` and `docs/glossary.md`.
AC1: worked example per figure type (§10). AC2: `XAxis.breaks` reserved (§11). AC3: approved
by Rob 2026-11-15. Decision D-20261115-01 (generic `Series` base).
T1.2 Quantities, units and x conversions (S007, commits `720bee9`, `f0a57bf`). All AC verified;
23 tests pass, ruff and mypy clean on Python 3.12.10.
T1.3 Spectrum and y kinds (S007). All AC verified; 45 tests pass. `GENERIC` series deferred to
v1.2 or later (D-20261116-01).
T1.4 Y transforms (S007). All AC verified; 58 tests pass. Log10 and Inverse give
`DerivedQuantity` (D-20261116-02). Extra order and domain tests added (68 tests in total).
T1.5 Region operations (S007). All AC verified; 98 tests pass.
T1.6 Canvas, panel and layer model (S008, commit `0e2fa4b`, merged as `00cbc7e`). All AC
verified; 172 tests pass, ruff and mypy clean. Stick layers raise `FeatureNotAvailable`
until T3.2. Interpretations approved by Rob (S008): see `LOGBOOK.md`.
T2.1 Delimited text reader (S009, merged as `0cb4b58`). AC1–AC3 verified; 214 tests pass, ruff
and mypy clean. **AC4 pending** until the corpus instrument files arrive (tested with synthetic
spectra meanwhile).
T2.2 Spreadsheet readers (S009, merged as `30f041f`). All AC verified; 226 tests pass, ruff and
mypy clean. `text.py` untouched (see `LOGBOOK.md`).
T2.3 Column mapping (S009, merged `Merge task/T2.3-column-mapping`). All AC verified; 248 tests pass,
ruff and mypy clean.
T2.4 Test corpus and harness (S011, merged `9805b55`). AC1 to AC5 verified; 258 tests pass, ruff and
mypy clean. Corpus: 1 real IR export, 17 synthetic, 4 artificial program outputs (skipped until the
parsers exist). Gallery: `python tools/run_corpus.py`.
T2.5 ORCA parsers (S013, merged `805b2ac`). All AC verified; 300 tests pass, ruff and mypy clean.
Support unclaimed (`VERIFIED_FAMILIES` empty) until a real ORCA file is in the corpus.
T2.6 Turbomole parsers (S013, merged `Merge task/T2.6-turbomole-parsers`). All AC verified; 327
tests pass, ruff and mypy clean. Support unclaimed (`VERIFIED_FAMILIES` empty).
T2.7 Single loading interface (S015, merged). All AC verified; 357 tests pass, ruff and mypy clean.
Theoretical tables become sticks; program outputs are always theoretical (UV-Vis in nm, IR in cm-1; was eV until S015 fix).
T3.1 Line shapes (S015, merged). All AC verified; 371 tests pass, ruff and mypy clean. Voigt via
the Faddeeva function; `voigt_fwhm` cites `olivero1977`, pending verification (in `literature/to-fetch.md`).
T3.2 Broadening (S016, merged `4a45111`). All AC verified; 401 tests pass, ruff and mypy clean.
FWHM only in cm-1/eV; grid FWHM/50, ±5 FWHM; stick layers now evaluated, sticks follow their
curve; lines ≤ 0 skipped. AC2 rewritten (D-20261122-02); nm view rule moved to T4.2 (-01).
T3.3 Scale factor and shift (S017, merged `16106e9`). All AC verified; 420 passed, 2 skipped,
ruff and `mypy src` clean. `x' = factor·x + shift` in cm-1/eV, IR and UV-Vis, before broadening;
sticks follow; imaginary lines not moved (D-20261122-07). References `scott1996`, `merrick2007`,
`irikura2005` pending.
T3.4 Absorptivity and Beer–Lambert (S018, merged `94782e2`). All AC verified; 456 passed, 2 skipped,
ruff and `mypy src` clean. f → ε from CODATA 2018 (2.315351e8, D-20261122-09; qclab's 2.315115e8 is
1.02e-4 low); km/mol → ε = 100/ln10; ε ↔ A with b (cm), c (mol/L). Sticks rule restated
(D-20261122-08, replaces -05): linear transforms commute with broadening, a stick on ε is its band
maximum; non-linear ones act on the curve. Derivations in `docs/theory.md`. `codata2018` pending.

## Tasks not started

All of `ROUTE.md` except T0.1–T0.4, T1.1–T1.6, T2.1–T2.7, T3.1–T3.4: T4.1–T4.6, T5.1–T5.2,
T6.1–T6.3, T7.1–T7.3, T8.1–T8.2, T9.1–T9.2, T10.1–T10.2, T11.1–T11.3, T12.1–T12.3,
T13.1–T13.4, T14.1–T14.2, T15.1–T15.4, T16.1–T16.6.

## Open decisions

| ID | Decision | Owner | Blocks |
|---|---|---|---|
| D-01 | Name of the app and of the package. Ideas in `notes/name-ideas.md`. Working name `graphing`. | Rob and group | T16.4 (and renaming gets costlier after E4) |
| D-02 | Who owns software written by UCR staff, and may it be released under GPL-3.0-or-later (code) and CC BY-SA 4.0 (texts and data), including code derived from `qclab-utilities`? The PI does not know. **Addressee is PROINNOVA (DIPROVID, Vicerrectoría de Investigación), not the Oficina Jurídica** (D-20261115-02). Query sent by Rob (scheduled in Gmail for 2026-11-16 08:00, to info.proinnova@ucr.ac.cr); awaiting reply. **Pending, not blocking** (D-20261114-11): Rob uses no UCR resources (no UCR-paid tools, no paid research time). It becomes blocking as soon as any UCR resource is used. | Rob | nothing, for now |
| D-08 | How beta testers (non-programmers) report bugs: GitHub issues, a form, e-mail to Rob…; and who the testers are. Beta = finished app given to a few people, bugs fixed, then public release (Rob, S008). | Rob | T16.6 |
| D-05 | Sources for the IR guide. Available: Wade 8th ed. (Appendix 2A chart, 2B table; text layer present), Vogel 5th ed. and Nakamoto 4th ed. (scanned, need OCR). Specialised references (Silverstein, Pretsch, Socrates) still to be found. | Rob | T8.1 |

Closed on 2026-11-14 (see `LOGBOOK.md`): licence for texts and data is CC BY-SA 4.0;
marking a stage done in `ROUTE.md` needs no authorisation; no "normalise to area".
Closed on 2026-11-17 (D-20261117-01, see `LOGBOOK.md` S010): D-07 — km/mol → ε exists; decadic ∫ε dν̃ [L mol⁻¹ cm⁻²] = (100/ln10)·A [km/mol] (program intensities are Napierian). T3.4 implements it. Sources: IUPAC Green Book 2023 §4.7.1 (typeset page still to verify) and ORCA 6.0 manual §6.12.
Closed on 2026-11-18 (D-20261118-01): D-09 — reference policy, now `CLAUDE.md` §13 (ACS bibliography in `docs/references.bib`; PDFs in git-ignored `literature/`; verification non-blocking, required before the beta).

## Pending inputs

**Re-verify against the public corpus (S012):** every parser developed on the local data in `tests/reference/` (including `meeting-20260918/`, real Turbomole files, unpublished) must be re-checked once publishable real files of the same kind are in `tests/corpus/`. Until then no support is claimed (§8.3).

| What | From | Needed by |
|---|---|---|
| PDFs listed in `literature/to-fetch.md` (9 now; new in S018: CODATA 2018) | Rob | non-blocking; all verified before T16.6 |
| **Corpus, theoretical:** ORCA and Turbomole outputs (TDDFT and frequencies) of a few small, well-known molecules, publishable. One set per program version the app should claim to support. | Rob / lab | T2.4, T2.5, T2.6 |
| **Corpus, experimental:** files exactly as real instruments export them, UV-Vis and IR, as txt, csv, xlsx, ods (some with decimal comma, some with preamble). The sample does not matter. | Kenneth | T2.1 AC4 (a real IR txt export is in; csv, UV-Vis, decimal comma still missing), T2.2 AC (xlsx, ods) |
| Specialised IR references | Rob | T8.1 |
| Reply from PROINNOVA to the D-02 query (ownership, GPL, CC BY-SA, which regulation applies) | PROINNOVA | before any UCR resource is used; before the first public push if in doubt |
| A macOS machine for manual testing | Rob | T15.4 |
| Lawsone-series spectra, dilution curves, photographs | Rob and lab | T16.2 |

## Data on disk

- `tests/reference/orca/`, `tests/reference/turbomole/`: outputs copied from
  `qclab-utilities` on 2026-11-13. Unpublished molecules: local only, git-ignored,
  extra local check. See `tests/reference/PROVENANCE.md`.
- `tests/reference/synthetic/`: synthetic inputs from `qclab-utilities/examples`;
  candidates for the corpus edge cases (move in T2.4, with Rob's confirmation).
- `tests/reference/experimental/`: empty.
- `tests/corpus/`: not created yet (T0.1 / T2.4).
- `brainstorming/`: session transcript and whiteboard photos. Not published.
- `notes/name-ideas.md`: name candidates.

## Known defects

| ID | Task | Defect | Status |
|---|---|---|---|
| X-01 | T2.1 | A malformed cell inside the numeric block silently truncated the table. | **Closed** S012: `MalformedCell` error, `fix/X-01-malformed-cell`, merged `a6b506c`. |
| X-02 | T2.2 | Same defect in the spreadsheet reader (empty or text cell inside the table). | **Closed** S012, same fix. |
| X-03 | T1.3 | `StickData` requires strictly ascending x: it cannot hold repeated positions (degenerate modes or states printed with equal values), nor file order. Found in S013. **Decisions D-20261118-02 and -03 (Rob):** keep every printed line as is; the display sums exactly equal lines always and unresolved lines (about 2 px, width-limited grouping) while they are unresolved, separating on zoom; broadened curve always from raw lines; export writes the original lines; option "sum sticks" per layer, default on, with "?" help; small mark on summed sticks accepted. Detail in `LOGBOOK.md` (S013). | **Closed** S015, `fix/X-03-stick-lines` (core part: `StickData` + `labels`, `Style.sum_sticks`, `core/sticks.py`, `LayerValues.sticks`). Render, selection and export parts: T4.2, T4.6, T6.2, T11.3. |
| X-04 | T2.6, T2.5, T2.1, T3.x | Confirmed, wider than first found (S019 sweep of every tracked file against `tests/reference/`). Copied from unpublished outputs (§8.4): Turbomole — the `ESCF` and `EXSPECTRUM` fixtures and the hard-coded values of the `local_data` tests in `test_parser_turbomole.py`; the first two rows and the header date of crq200 `exspectrum` in `tests/corpus/theoretical/{artificial,broken-row,no-header}.exspectrum`, their sidecar and `tools/make_synthetic.py`. ORCA — rows of orca-601-tddft and orca-601-freq in `TEXT_6X`/`TEXT_IR` of `test_parser_orca.py` and in `tests/integration/test_io.py`, and the values in its `local_data` tests. `test_sticks.py` — two wavenumbers of meeting-20260918 `vibspectrum`. All in the 72 unpushed commits: a fix commit alone would still publish them through history. | **Fixed** (S019, approved by Rob): synthetic values everywhere; local-data expectations moved to `tests/reference/expected-values.json` (git-ignored); the 72 unpushed commits squashed into one (`feat: stages E1-E3`), old history kept only in the local branch `backup/pre-X-04`, which must never be pushed. Leak sweep clean. |
