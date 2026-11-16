# STATE.md — Current state of `graphing`

> Read at the start of every session, after `CLAUDE.md`. Maintained without prior
> approval; every change is reported.

Last updated: 2026-11-15T22:30-06:00 · Session S006 (closing)

## Next action

**T1.2** (Quantities, units and x conversions; model **Sonnet**). Follow
`docs/architecture.md` §3.1 and §3.5. Present the plan to Rob, wait for approval.

CLAUDE.md §6.3/§6.4 revised with Rob's R3 authorisation (S006, commit `fa187fe`).

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

## Tasks not started

All of `ROUTE.md` except T0.1–T0.4 and T1.1: T1.2–T1.6, T2.1–T2.7, T3.1–T3.3, T4.1–T4.6, T5.1–T5.2,
T6.1–T6.3, T7.1–T7.3, T8.1–T8.2, T9.1–T9.2, T10.1–T10.2, T11.1–T11.3, T12.1–T12.3,
T13.1–T13.4, T14.1–T14.2, T15.1–T15.4, T16.1–T16.4.

## Open decisions

| ID | Decision | Owner | Blocks |
|---|---|---|---|
| D-01 | Name of the app and of the package. Ideas in `notes/name-ideas.md`. Working name `graphing`. | Rob and group | T16.4 (and renaming gets costlier after E4) |
| D-02 | Who owns software written by UCR staff, and may it be released under GPL-3.0-or-later (code) and CC BY-SA 4.0 (texts and data), including code derived from `qclab-utilities`? The PI does not know. **Addressee is PROINNOVA (DIPROVID, Vicerrectoría de Investigación), not the Oficina Jurídica** (D-20261115-02). Query sent by Rob (scheduled in Gmail for 2026-11-16 08:00, to info.proinnova@ucr.ac.cr); awaiting reply. **Pending, not blocking** (D-20261114-11): Rob uses no UCR resources (no UCR-paid tools, no paid research time). It becomes blocking as soon as any UCR resource is used. | Rob | nothing, for now |
| D-05 | Sources for the IR guide. Available: Wade 8th ed. (Appendix 2A chart, 2B table; text layer present), Vogel 5th ed. and Nakamoto 4th ed. (scanned, need OCR). Specialised references (Silverstein, Pretsch, Socrates) still to be found. | Rob | T8.1 |

Closed on 2026-11-14 (see `LOGBOOK.md`): licence for texts and data is CC BY-SA 4.0;
marking a stage done in `ROUTE.md` needs no authorisation; no "normalise to area".

## Pending inputs

| What | From | Needed by |
|---|---|---|
| **Corpus, theoretical:** ORCA and Turbomole outputs (TDDFT and frequencies) of a few small, well-known molecules, publishable. One set per program version the app should claim to support. | Rob / lab | T2.4, T2.5, T2.6 |
| **Corpus, experimental:** files exactly as real instruments export them, UV-Vis and IR, as txt, csv, xlsx, ods (some with decimal comma, some with preamble). The sample does not matter. | Kenneth | T2.4, T2.1 AC4, T2.2 |
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

None.
