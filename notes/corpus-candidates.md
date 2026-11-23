# Candidate molecules for the theoretical corpus

Working note (S011). Small, neutral molecules with only C, H, O, N, S, P, whose
ORCA and Turbomole outputs would enter the public corpus (CLAUDE.md §8.2-8.3). The
chemistry does not matter for the corpus; the layout of each program's output does.
Nothing here is run yet: the group's cluster is unavailable.

- **IR (frequencies), fast:** H2O, CO2 (linear, degenerate modes), NH3, H2S, SO2, PH3,
  H2CO, CH3OH. Gas-phase experimental IR spectra exist for these in [nistwebbook]
  (its terms of use for redistributing the spectra are not checked).
- **UV-Vis (TDDFT), medium:** H2CO, acetone, benzene, pyridine, pyrazine, thiophene,
  phosphinine (C5H5P). Many of these belong to the small-molecule excited-state
  benchmark set of [schreiber2008]; whether each one does is not checked.
- **Coloured compounds:** p-nitroaniline, azobenzene, indigo, p-benzoquinone, lawsone
  (C10H6O3, ties in with the group's own spectra).
- **Pharmacy teaching examples:** paracetamol, caffeine, aspirin (UV and IR are easy to
  measure in a teaching lab).

Minimum useful set, one family per program: ORCA 6.x (H2CO TDDFT; H2O and CH3OH
frequencies), Turbomole 7.x (H2CO `exspectrum`; CO2 and H2S `vibspectrum`), and an
ORCA 4.x TDDFT of H2CO if 4.x support is to be claimed. Versions to claim: undecided.

References: see `docs/references.bib`.
