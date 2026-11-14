# Contributing

Thank you for helping with graphing. These are the rules for branches, commits and
records. Development follows the task plan in `ROUTE.md` and the working rules in
`CLAUDE.md`.

## Set-up

Create a virtual environment outside the project folder (see the README), and install
the project with its development extras:

```bash
~/graphing-venv/bin/python -m pip install -e ".[dev]"
```

Before you propose a change, these must all pass:

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

## Branches

- One branch per task: `task/<ID>-<slug>`, for example `task/T0.3-project-documents`.
- Fixes for defects found after a task was approved: `fix/<ID>-<slug>`.
- Branches are merged into `main` only when the task is approved, and `main` must always
  pass the full test suite.
- Tasks are executed one at a time, in dependency order. Two tasks never edit the same
  file at the same time.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`,
`docs:`, `test:`, `refactor:`, `chore:`, `build:` or `ci:`. Put the task ID in the
subject:

```
feat(core): T1.2 unit conversions
```

Keep each commit to one change. Update `CHANGELOG.md` in the same commit as the change
it describes, under `Unreleased`.

## Code

- Every source file starts with the SPDX header
  `# SPDX-License-Identifier: GPL-3.0-or-later`.
- Code, comments, docstrings and developer documentation are in English.
- Type hints on every function signature. NumPy-style docstrings on every public
  function and class.
- `graphing.core` imports nothing from `graphing.render` or `graphing.gui`, and
  `graphing.render` imports nothing from `graphing.gui`.
- User-visible text is never hard-coded: it is wrapped for translation.
- Every new user-facing parameter needs a plain-language help entry in the three
  supported languages.

## Data

Do not add unpublished measurements, unpublished molecules or personal data to the
repository. Public test spectra go in `tests/corpus/` with a sidecar file describing
the program or instrument, its version, and the expected result. A file enters the
corpus only when its owner confirms that it may be published.

## Licence

By contributing, you agree that your contribution is licensed under GPL-3.0-or-later.
