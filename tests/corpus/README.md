# Test corpus

Public, growing library of spectra used to prove that graphing reads every input layout
it claims to read. See `CLAUDE.md` §8 for the policy.

- `experimental/`: files exactly as a real instrument exports them.
- `theoretical/`: outputs of quantum chemistry programs (artificial ones for now).
- `synthetic/`: files made on purpose, including files that must fail.

Every data file has a sidecar `<file>.corpus.json` with: `source` (program or
instrument, version, molecule, producer), `publishable` (Rob's confirmation),
`reader` (`text`, `sheet`, or a parser name), optional `settings`, `sheet` and
`mapping`, and `expect` (`table`, `spectra`, or an `error` with its stage and type).

Run everything with `python tools/run_corpus.py`; the gallery is written to
`build/corpus-gallery/index.html`. The synthetic files are regenerated with
`python tools/make_synthetic.py`.
