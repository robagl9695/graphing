# graphing

A free, open-source desktop application with a graphical interface to plot and
analyse experimental and theoretical UV-Vis and IR spectra, without writing commands.

It is aimed at university students and teachers who have no programming training.
It reads stick spectra from quantum chemistry programs and broadens them, overlays
theory and experiment, computes the perceived colour of a UV-Vis spectrum, and shows
an orientative guide of typical IR ranges.

## Status

**In development. There is no public release yet.** The current version is `0.1.0`.
The repository holds the project foundation (layout, configuration, test set-up); the
interface and the spectral calculations are not yet built.

The planned work is organised in stages in `ROUTE.md`, and the state of each task is
in `STATE.md`.

## Running from source

Requirements: Python 3.12 or later.

```bash
python -m venv ~/graphing-venv
~/graphing-venv/bin/python -m pip install -e ".[dev]"
~/graphing-venv/bin/python -m pytest
```

On Windows, use `%USERPROFILE%\graphing-venv\Scripts\python.exe` in place of
`~/graphing-venv/bin/python`.

Create the virtual environment outside the project folder. It holds tens of thousands
of files, which slows down any folder that a cloud service synchronises.

## Licence

Copyright (C) the graphing contributors.

The code is free software, licensed under the GNU General Public License,
version 3 or (at your option) any later version (GPL-3.0-or-later). See
[LICENSE](LICENSE).

The manual, the help texts and the IR range guide data will be released under
CC BY-SA 4.0.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch and commit rules.
