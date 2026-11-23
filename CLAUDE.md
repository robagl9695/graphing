# CLAUDE.md — Working instructions for `graphing`

> **Every session starts by reading this file and `STATE.md`, nothing else.**
> `ROUTE.md` and `LOGBOOK.md` are read on demand only (see §2).
> This file overrides any default assumption.

Last revised: 2026-11-18 · Working name of the app: `graphing` (final name: open decision D-01)

---

## 1. What this project is

A free, open-source desktop application with a graphical interface to plot and analyse
**experimental and theoretical UV-Vis and IR spectra** without writing commands.

- **Audience:** university students and teachers (Chemistry, Pharmacy and related
  degrees, mainly in Latin America) who have no programming training and no access to
  paid software. Assume the user does not know what a line shape or FWHM is.
- **What makes it different:** it reads stick spectra from quantum chemistry programs
  and broadens them; it overlays theory and experiment; it computes the perceived
  colour of a UV-Vis spectrum; it shows an orientative guide of typical IR ranges.
- **Guiding idea:** drag a file in, make two or three choices, get a plot.
- **Design model:** layers on shared axes, as in ggplot2 (§6.3).

It is independent of `qclab-utilities`. Code from that repository (`common/cie.py`,
`srgb.py`, `lineshapes.py`, `peaks.py`, `parsers/`, `utils/colorcoords/core.py`) may be
used as a starting point and must be modernised: it was written for Python 3.5.

---

## 2. Session protocol

**Open**

1. Read `CLAUDE.md` and `STATE.md`.
2. Take the task named under "Next action" in `STATE.md`. Do not pick another one.
3. Read **only that task's block** in `ROUTE.md` (search by task ID; do not read the
   whole file).
4. Check that the active model is the one assigned to the task (§5). If it is not,
   say so and stop.
5. State in two or three lines what will be done, then follow the task cycle (§4).

**Read `ROUTE.md` or `LOGBOOK.md` only when** a specific question cannot be answered
by `CLAUDE.md`, `STATE.md` or Rob. Search for the task ID, decision ID or keyword;
never load either file whole.

**Close**

1. Append the session entry to `LOGBOOK.md` (§10).
2. Update `STATE.md`.
3. Report both in the closing message, with what was done, what failed and what is next.
4. If the tree is clean and tests pass, remind Rob to let Dropbox finish syncing
   before opening the folder on another machine.

---

## 3. Interaction rules

| # | Rule |
|---|---|
| **R1** | Propose first, wait for Rob's explicit approval, then execute. This covers everything the project produces: code, tests, data files, manuals, help texts, configuration, installers, and any structural decision. |
| **R2** | **Bookkeeping exception.** `LOGBOOK.md`, `STATE.md` and `literature/to-fetch.md` are written and kept up to date without asking, and so is the `verified` field of `docs/references.bib` (§13). Every change is reported in the same reply. |
| **R3** | `CLAUDE.md` and `ROUTE.md` are changed **only with Rob's express authorisation**. Propose the exact diff and wait. One exception: marking a stage as done in the progress table of `ROUTE.md` when the stage is approved needs no authorisation; it is reported like bookkeeping. |
| **R4** | Explain the reasoning and the intermediate steps, not just the result. Name the alternatives considered and why they were discarded. |
| **R5** | When something is ambiguous or unknown, ask. Do not assume and do not invent facts about file formats, programs or instruments. |
| **R6** | Ask questions as plain text inside the message. Never use interactive question widgets. |
| **R7** | Conversation with Rob is in Spanish. Everything in the repository is in English (§7), except user-facing translations, the manuals and `docs/acceptance-checklist.md`, which is written in Spanish. |
| **R8** | Nothing is a final product. Every deliverable is living, reviewable material. |
| **R9** | A decision recorded in `LOGBOOK.md` is not changed silently. To revise it, open a new decision that references the old ID. |
| **R10** | Once a task is approved, do not reopen it inside another task. If later work reveals a defect in it, record it in `STATE.md` as a defect and ask. |

---

## 4. Work cycles

Testing happens at two levels. The **task cycle** proves that one piece works. The
**integration cycle** proves that the pieces work together and that the whole app
still works. Passing the first never replaces the second.

### 4.1 Task cycle

Every task in `ROUTE.md` goes through the same cycle. A task is closed only when
**all** its acceptance criteria pass.

1. **Plan.** Restate the objective, list the files to create or change, and the
   approach. Present it to Rob and wait for approval (R1).
2. **Set up.** Create the branch `task/<ID>-<slug>` from `main`. Add fixtures.
3. **Execute.** Implement only what the task block says. No extra features, no
   refactoring outside the task's files.
4. **Test.** Run the tests named in the task block, then the whole suite, `ruff` and
   `mypy`.
5. **Evaluate.** Go through the acceptance criteria one by one and report pass or
   fail for each, with the evidence (test name, command output).
6. **Decide.**
   - All pass: commit, merge to `main`, update `STATE.md`, log it. The task is approved.
   - Any fail: go back to step 1 with the failure as input.
   - Three failed cycles on the same task: stop and escalate to Rob with a diagnosis.
     Do not keep trying.

Acceptance criteria are never weakened to make a task pass. If a criterion turns out
to be wrong, that is a `ROUTE.md` change and needs R3.

### 4.2 Integration cycle (whole app)

Run **at the end of every stage**, before the stage is approved, and again in full
before every tagged version. It has the same shape as the task cycle (plan, set up,
execute, test, evaluate, repeat until everything passes) and tests the app as a whole:

| Level | What it checks | Where | From |
|---|---|---|---|
| **Regression** | Every test of every earlier stage still passes. | whole suite | E0 |
| **Integration** | Complete chains through the public interfaces of `core/` and `render/`, with no GUI: file → reader → model → transforms → figure → export. | `tests/integration/` | E2 |
| **Corpus** | Every file of the test corpus (§8) is loaded, processed and plotted without error, and a gallery of the resulting figures is produced for Rob to look through. | `tests/corpus/` | E2 |
| **End to end** | Scripted user journeys through the real interface, each one crossing several stages (e.g. import a theoretical file, broaden it, paste an experimental one on top, normalise, pick peaks, export). | `tests/e2e/` | E4 |
| **Installed app** | The same journeys, reduced, on the frozen app on each system. | CI smoke job | E15 |
| **Acceptance** | Rob and the group use the installed app as users against `docs/acceptance-checklist.md`. | the checklist | in full before the beta; the items touched by a change at every later version tag |

Rules:

- Each stage **adds** its own integration tests and at least one end-to-end journey
  that combines the new stage with earlier ones. The journeys are listed in
  `docs/test-scenarios.md`; the list only grows.
- From E4, every task that adds or changes something the user sees appends its items
  to `docs/acceptance-checklist.md` in the same commit (what the user does, what they
  must see, which task makes it possible). The list only grows; changing an item
  needs a new decision (R9). A GUI task that adds a function without its checklist
  items fails.
- A stage is approved only when all its tasks are approved, its gate in `ROUTE.md`
  passes, **and** the integration cycle is green.
- When the integration cycle fails, the failure is traced to the task that owns the
  faulty code, recorded in `STATE.md` as a defect, and fixed through the task cycle
  (§4.1) on a `fix/` branch. Then the integration cycle is run again from the start.
- A failure that cannot be attributed to one task is an architecture problem: stop
  and consult Rob (§5, Opus + Rob).

---

## 5. Model assignment

Each task block in `ROUTE.md` names its model. The rule behind the assignment:

| Model | Used for |
|---|---|
| **Haiku** | Well-defined, low-reasoning, simple or repetitive work: boilerplate, config files, transcribing tables, renaming, mechanical extraction. |
| **Sonnet** | Standard implementation, running and evaluating tests, specific features, simple debugging. |
| **Opus** | Everything else: refactoring, advanced implementation, medium and advanced debugging, numerical validation, complex reasoning, and all user-facing text (help, manual, translations drafts). |
| **Opus + Rob** | Architecture changes, or changes with significant impact on a large part or a central function of the project (data model, renderer, project file format, packaging). Fable is **not** available on this plan, so: Opus prepares the proposal, **stops**, and Rob decides before anything is executed. |

Token economy:

- Read only the files the task needs. Prefer searching to reading whole files.
- Do not re-derive context that `STATE.md` already gives.
- Use a subagent only for a self-contained subtask, on the cheapest model that can do
  it, and only when it saves context in the main session.
- Do not restate the plan, the diff or the test output more than once.
- If a task turns out to be harder than its assigned model can handle, stop and ask
  to move it up one level. Do not burn cycles.

---

## 6. Architecture

### 6.1 Stack

- Python ≥ 3.12.
- GUI: **PySide6** (Qt 6).
- Plotting: **Matplotlib**, embedded with the QtAgg backend.
- Numerics: **NumPy**, **SciPy**.
- File reading: `openpyxl` (xlsx), `odfpy` (ods), own reader for txt/csv. **No pandas.**
- Optional: **RDKit** for 2D structures. The app must start and work without it.
- Development: `pytest`, `pytest-qt`, `ruff` (lint and format), `mypy`.
- Packaging: PyInstaller plus one installer per system, built in GitHub Actions.

Adding a runtime dependency is an architecture change (§5, Opus + Rob).

### 6.2 Layers

```
graphing/                    repository root
├── CLAUDE.md  ROUTE.md  STATE.md      governance files (published)
├── LOGBOOK.md                         project log (NOT published)
├── README.md  LICENSE  CHANGELOG.md  CONTRIBUTING.md  pyproject.toml
├── src/graphing/
│   ├── core/          no Qt, no Matplotlib: data model, units, transforms, readers,
│   │                  parsers, line shapes, peaks, colour, IR guide data access
│   ├── render/        core model -> Matplotlib figure. No Qt widgets.
│   ├── gui/           PySide6 widgets and dialogs. No numerical logic.
│   ├── translations/  the interface texts in each language (see below)
│   └── resources/     icons, IR guide data, help texts
├── tests/
│   ├── unit/  gui/  integration/  e2e/
│   ├── corpus/        public test spectra (§8)
│   └── reference/     unpublished files, local only (NOT published)
├── docs/              architecture, interface spec, theory, test scenarios, manual
├── tools/             scripts: translation round trip, corpus gallery, builds
├── notes/             working notes for the group
├── build/             everything a build produces: executables and installers
│                      (NOT published; generated, never edited by hand)
├── literature/        PDFs of cited sources and the to-fetch list (NOT published, §13)
└── brainstorming/     session transcript and photos (NOT published)
```

What `translations/` holds:

- **The text catalogues**: one table of interface texts per language, in two
  equivalent forms — a spreadsheet (`context | English | Español | Português`) that
  people edit, and Qt's text files (`.ts`) generated from it.
- **The loadable catalogues** (`.qm`): the same tables converted by a script into
  the binary form the running app reads. They are data files, not programs, they are
  generated automatically from the `.ts` files, and nobody edits them.

Hard rules:

- `core/` imports nothing from `render/` or `gui/`. `render/` imports nothing from `gui/`.
- Every calculation lives in `core/` and is unit-tested without a display.
- The GUI never changes data directly: it calls `core/` operations and re-renders.
- User data is never modified in place. Raw data is kept; transforms are stored as
  parameters and applied on render.

### 6.3 Data model

```
Project
└── Canvas            one figure; a proportional grid (spans, nesting) of panels
    └── Panel         one plot
        ├── x axis    quantity, unit, limits, inverted, secondary x axis
        │             (breaks: reserved, v1.1)
        ├── y axis (left), optional y axis (right); each with its layer arrangement
        ├── Layer…    one series each, drawn against the left or right y axis
        └── Inset…    zoom inset (live view of the host) or free inset (own panel)
```

Full specification: `docs/architecture.md`. Terms: `docs/glossary.md`.

- The base data type is a generic x–y **Series** (D-20261115-01). A **Spectrum**
  specialises it with a technique (UV-Vis or IR) and an origin (theoretical or
  experimental). **The user declares both; the app never guesses and never warns.**
- A theoretical spectrum stores its sticks plus the broadening parameters (line
  shape, FWHM, frequency scale factor). The curve is always recomputed from them.
- **Inheritance (ggplot2 rule):** the first layer of a panel sets the x and y
  quantities and units. Every layer added later is converted to them. Changing an
  axis from its title changes it for all layers of that panel.
- **Normalisation is computed per layer**, according to the layer arrangement of the axis.
- Layer arrangement of a y axis: `overlap`, `normalised overlap`, `stacked` (gap
  per axis, overridable per layer). `stacked` may be combined with normalisation.
- Layers with incompatible y (different technique or quantity) share an axis only
  normalised, or go to the other side of a double y axis.
- A layer pasted into another canvas is an independent copy.
- Combination rules: `stacked` excludes a second y axis; an inset cannot contain an
  inset; subplots combine with everything.

The single-panel case is the priority: it must be complete and polished before
double axis, subplots and insets are built. The model supports all of them from the
start so that adding them changes no existing interface.

### 6.4 Scope

| Version | Content |
|---|---|
| **v1.0** | Readers txt/csv/xlsx/ods · ORCA and Turbomole parsers · Gaussian, Lorentzian and Voigt broadening · frequency scale factor · unit conversion on x · normalisation, levelling, T↔A, log and inverse on y · zoom, pan, crop in x and y · peak picking (auto, manual, label thinning) · overlap, normalised overlap, stacking · double y axis, subplots, inset · IR range guide · colour (XYZ, RGB, hex, with concentration) · structure image and SMILES · save/open project · export figure and data · es/en/pt interface, help and manual · installers for Windows, macOS, Linux |
| **v1.1** | Axis gap · plot digitizer · Gaussian and MOPAC parsers |
| **v1.x (possible)** | Plotting generic x–y data (the model already supports it) |
| **Later** | More features, taking [InstaNANO](https://instanano.com/) as a reference for what users of paid plotting services expect |
| **Out** | Baseline editing or fitting (only constant levelling exists) · proprietary instrument formats · 3D structures |

---

## 7. Code standards

- **English everywhere in the repository:** code, comments, docstrings, commit
  messages, these four files, developer documentation.
- PEP 8 via `ruff format`; `ruff check` and `mypy` clean on every commit.
- Type hints on every function signature. NumPy-style docstrings on every public
  function and class.
- Small functions with one job. Names that say what they hold, with units where
  relevant (`wavenumber_cm1`, `fwhm_ev`).
- Physical constants and conversion factors live in one module, each with its source.
- Explicit handling of bad input (missing file, malformed number, wrong column) with
  a message that names what was wrong. No bare `except`.
- No network access at runtime. No telemetry.
- Comments explain why, not what.
- Default plot colours: Rob's EQ figure palette, in this order — blue `#0A5199`,
  red `#AA1E1E`, purple `#8753C6`, amber `#BF7B00`, green `#007D50`.

---

## 8. Testing and data policy

### 8.1 Tests

- Every `core/` function has unit tests. Numerical tests state their tolerance.
- GUI behaviour is tested with `pytest-qt` on the offscreen platform.
- The full suite runs in CI on Windows, macOS and Linux.
- Whole-app testing follows the integration cycle (§4.2).

### 8.2 What the test data is for

This is plotting software. Test data exists to prove that the app **reads every
input layout it claims to read and produces the expected outputs**. It does not need
to be chemically interesting. Two things follow:

- **Theoretical inputs:** what matters is the layout each program version writes.
  Calculations of small, well-known molecules are enough, and they can be published.
- **Experimental inputs:** what matters is the file exactly as a real instrument
  exports it (preamble, separators, decimal comma, column order). The sample measured
  is irrelevant.

### 8.3 The corpus

`tests/corpus/` is a growing, **public** library of spectra of known molecules:
program outputs (ORCA, Turbomole) and instrument exports (txt, csv, xlsx, ods), each
with a small sidecar file recording program or instrument, version, molecule, who
produced it and the expected result (number of transitions or modes, first and last
values, or "must fail with error X").

- The corpus harness runs every file through load → process → plot → export and
  fails if any file breaks. It also writes a gallery of figures for visual review.
- **Verified support:** the app claims to read a (program, format) pair only when the
  corpus contains a real file of that kind that is read correctly. Support is declared
  per major-version family (e.g. "ORCA 6.x").
- Small synthetic files are used in addition, for cases real data does not offer
  (imaginary mode, malformed number, empty block).
- A file enters the corpus only when Rob confirms it can be published.

### 8.4 What is not published

- `tests/reference/` holds the outputs copied from `qclab-utilities` on 2026-11-13.
  They are calculations of **unpublished molecules**, so they stay on Rob's disk and
  are git-ignored. This restriction is about those files, not about real calculations
  in general. Tests that use them carry the marker `local_data` and are skipped with a
  clear message when the files are absent; they are an extra local check, never a
  requirement for a task to pass.
- `LOGBOOK.md`, `brainstorming/`, `build/` and `literature/` are git-ignored as well.

---

## 9. Versioning and git

- **Semantic Versioning**, `X.Y.Z`. The version lives in one place
  (`pyproject.toml`). When each number goes up:

  | Number | Goes up when | Examples |
  |---|---|---|
  | **Z** (patch) | A defect is fixed and nothing else changes: no new function, no change to file formats or to what the user sees beyond the fix. | wrong unit label; parser crash on a blank line |
  | **Y** (minor) | Something is **added** and everything that worked before still works the same way: a new tool, a new input format or program version, a new language, a new export format. Z returns to 0. | IR guide added; MOPAC parser added |
  | **X** (major) | Something that worked before **stops working or changes meaning**: project files saved by the previous version cannot be opened without loss, a function or input format is removed, a default changes the numbers a user gets. Y and Z return to 0. | new project-file layout without migration |

  - Before the first public release the version is `0.Y.Z`: Y goes up at the stage
    gates listed in the `ROUTE.md` progress table, Z for fixes made between gates.
  - `1.0.0` is the first public release: the full v1.0 scope, installers for the three
    systems, manual in three languages.
  - Beta versions are marked `-beta.N` (`1.0.0-beta.1`): the finished app given to a
    few testers, whose bug reports are fixed before the release candidates.
  - Release candidates are marked `-rc.N` (`1.0.0-rc.1`).
  - Approving a task does not change the version by itself. Changes wait under
    "Unreleased" in `CHANGELOG.md` until the next gate or fix release.
  - The project-file schema has its own integer version, independent of the app's.
  - Raising **X** always needs Rob's express authorisation.
- **Conventional Commits** (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`,
  `chore:`, `build:`, `ci:`), with the task ID in the subject: `feat(core): T1.2 unit conversions`.
- One branch per task, `task/<ID>-<slug>`, merged to `main` only when the task is
  approved. `main` always passes the full suite.
- `fix/<ID>-<slug>` branches for defects found after a task was approved.
- Tasks are executed one at a time, in dependency order. Two tasks never edit the
  same file concurrently.
- `CHANGELOG.md` in Keep a Changelog format, updated in the same commit as the change.
- A tag `vX.Y.Z` on `main` every time the version changes, after the integration
  cycle (§4.2) is green.
- The repository is **public** on GitHub. Published: source, tests, the corpus,
  `CLAUDE.md`, `ROUTE.md`, `STATE.md`, documentation. Not published: `LOGBOOK.md`,
  `brainstorming/`, `build/`, `tests/reference/`, `literature/`.
- The working folder is inside Dropbox. Run git from one machine at a time and let
  Dropbox finish syncing before switching.

---

## 10. Bookkeeping formats

**`LOGBOOK.md`** — append-only, newest entry at the bottom. One entry per session:

```
## 2026-11-13T23:55-06:00 · S001 · <one-line title>
**Model:** … · **Tasks:** …
### Done
### Discussed
### Decisions        (IDs: D-YYYYMMDD-NN)
### Problems / defects
### Next
```

An entry is never rewritten. Corrections go in a later entry under "Errata".

**`STATE.md`** — always reflects the present. Sections, in this order: next action;
work priority; tasks in progress; tasks done; tasks not started; open decisions;
pending inputs; known defects. Keep it under two screens: it is read every session.

---

## 11. Text for users

- Interface source strings are written in English and wrapped for translation from
  the first line of GUI code. No hard-coded user-visible text.
- Translations (es, pt) are edited by people in a spreadsheet (`context | English |
  Español | Português`); scripts convert between the spreadsheet and the Qt
  translation files. Claude drafts the Spanish; Rob reviews it. Portuguese is done by
  a collaborator.
- **Every parameter the user can set has a "?" help entry** in plain language, in the
  three languages. A GUI task that adds a parameter without its help entry fails.
- Help and manual are written first in Spanish for Rob's review, then in English and
  Portuguese. The manual is built with LaTeX.
- The IR range guide is orientative. Its text must never say that a band "is" a
  given group; it shows where to look.

---

## 12. Licence

- Code: **GPL-3.0-or-later**. Every source file carries the SPDX header
  `# SPDX-License-Identifier: GPL-3.0-or-later`.
- Manual, help texts and the IR guide data: **CC BY-SA 4.0**.
- The IR guide is compiled from several cited sources with its own layout. No table
  or figure is copied from a book.
- Open legal question (UCR Oficina Jurídica) is tracked in `STATE.md`.

---

## 13. References

Decision D-20261118-01 (closes open decision D-09).

- **One bibliography.** `docs/references.bib` (BibTeX, published). Every source cited
  anywhere in the repository (code, `docs/`, manual, help texts, IR guide data) has an
  entry there and is cited by its key. The file is created with the first citation.
- **Style: ACS.** The manual uses biblatex with the `chem-acs` style. Markdown documents
  (`docs/theory.md`) cite `[key]` and end with a reference list in ACS format. Code cites
  the key in the comment or docstring, e.g. `# Source: [iupac2023], section 4.7.1`.
- **Verification never blocks work.** Each entry carries a field
  `verified = {pending}` or `verified = {YYYY-MM-DD; literature/<key>.pdf; what was checked}`.
  A pending entry may be used. When Claude cites a source whose PDF is not in
  `literature/`, it adds it to `literature/to-fetch.md` (reference, DOI or URL, where it
  is cited, what to check). When Rob adds the PDF, Claude verifies the entry in the next
  session, updates `verified`, removes it from the list and reports. An error found this
  way is recorded as a defect (R10).
- **Release gate.** Every entry cited in published text is verified before the beta
  (T16.6).
- **Source hierarchy** for constants, conventions and acceptance criteria: standards
  (IUPAC, CODATA, BIPM) > program manuals and primary articles > textbooks > secondary
  sources (blogs, lecture notes, other groups' notes). Secondary sources may support a
  claim, never stand alone.
- **No invented bibliographic data** (R5). Anything written from memory is `pending`.
- `literature/` holds the PDFs, named `<key>.pdf`. It is git-ignored: the PDFs are
  copyrighted.
