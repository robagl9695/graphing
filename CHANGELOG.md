# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repository scaffold: package layout, `pyproject.toml`, test folders and
  governance files (`CLAUDE.md`, `ROUTE.md`, `STATE.md`). (T0.1)
- Lint, format and type configuration: `ruff` and `mypy` (strict on `graphing.core`),
  pytest markers, and skipping of `local_data` tests when their data is absent. (T0.2)
- Project documents: `LICENSE` (GPL-3.0), `README.md`, `CHANGELOG.md` and
  `CONTRIBUTING.md`. (T0.3)
- Continuous integration: GitHub Actions workflow running ruff, mypy and pytest on
  Linux, Windows and macOS with Python 3.12. (T0.4)
