# SPDX-License-Identifier: GPL-3.0-or-later
"""Run every file of the test corpus through the pipeline and write a gallery.

Usage::

    python tools/run_corpus.py [--corpus DIR] [--gallery DIR]

Files are found through their sidecars (``<file>.corpus.json``); adding a file to
the corpus needs a sidecar and no change here. For each file the harness runs the
stages *load*, *map*, *plot* and *export* (program outputs: *parse*, *broaden*, *plot*
and *export*), and compares the outcome with the sidecar's ``expect`` block. A stage
whose code does not exist yet is skipped with a message, so the harness works from
stage E2 and grows as later stages are built.

The exit status is 1 when any file fails, and the failing files are named.
"""

from __future__ import annotations

import argparse
import html
import importlib
import importlib.util
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:  # allow running without installing the package
    sys.path.insert(0, str(ROOT / "src"))

SIDECAR_SUFFIX = ".corpus.json"
IGNORED_NAMES = {"README.md"}
IGNORED_SUFFIXES = {".py", ".pyc"}
RTOL = 1e-9

# Readers that exist as modules, by the name a sidecar gives them. A reader not
# importable yet (a parser of a later task) makes the file "skipped", not failed.
READER_MODULES = {
    "text": "graphing.core.readers.text",
    "sheet": "graphing.core.readers.sheet",
    "orca": "graphing.core.parsers.orca",
    "turbomole-vibspectrum": "graphing.core.parsers.turbomole",
    "turbomole-exspectrum": "graphing.core.parsers.turbomole",
    "turbomole-escf": "graphing.core.parsers.turbomole",
}


@dataclass
class FileResult:
    """Outcome of one corpus file."""

    path: Path
    status: str = "pass"  # "pass", "fail" or "skip"
    messages: list[str] = field(default_factory=list)
    stages: dict[str, str] = field(default_factory=dict)
    figure: Path | None = None

    def fail(self, message: str) -> None:
        self.status = "fail"
        self.messages.append(message)


def module_available(name: str) -> bool:
    """Whether a module can be imported (False when a parent package is missing)."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def discover(corpus: Path) -> tuple[list[Path], list[Path]]:
    """Return ``(sidecars, files_without_sidecar)`` under ``corpus``."""
    sidecars = sorted(corpus.rglob(f"*{SIDECAR_SUFFIX}"))
    orphans = []
    for path in sorted(corpus.rglob("*")):
        if not path.is_file() or path.name.endswith(SIDECAR_SUFFIX):
            continue
        if path.name in IGNORED_NAMES or path.name.startswith("."):
            continue
        if path.suffix in IGNORED_SUFFIXES or "__pycache__" in path.parts:
            continue  # the harness's own tests live in the corpus folder
        if not path.with_name(path.name + SIDECAR_SUFFIX).exists():
            orphans.append(path)
    return sidecars, orphans


def data_path(sidecar: Path) -> Path:
    """The data file a sidecar describes."""
    return sidecar.with_name(sidecar.name[: -len(SIDECAR_SUFFIX)])


def run_file(sidecar_path: Path, root: Path) -> tuple[FileResult, list[Any]]:
    """Run one file; return its result and the spectra built (for the gallery)."""
    path = data_path(sidecar_path)
    result = FileResult(path=path)
    spectra: list[Any] = []
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        result.fail(f"sidecar cannot be read: {error}")
        return result, spectra

    problems = check_sidecar(sidecar, path)
    for problem in problems:
        result.fail(problem)
    if problems:
        return result, spectra
    if not path.exists():
        result.fail("the data file named by the sidecar does not exist")
        return result, spectra

    expect = sidecar["expect"]
    module_name = READER_MODULES.get(sidecar["reader"])
    if module_name is None:
        result.fail(f"unknown reader '{sidecar['reader']}'")
        return result, spectra
    if not module_available(module_name):
        result.status = "skip"
        result.stages["load"] = (
            f"skipped: reader '{sidecar['reader']}' is not built yet"
        )
        result.messages.append(result.stages["load"])
        return result, spectra

    if sidecar["reader"] == "orca" or sidecar["reader"].startswith("turbomole"):
        spectra = parse_stage(sidecar, path, expect, result)
        if spectra and result.status != "fail":
            if module_available("graphing.core.broadening"):
                spectra = broaden_stage(sidecar, path, result) or spectra
            else:
                result.stages["broaden"] = "skipped: broadening is not built yet"
        result.stages["export"] = "skipped: export is not built yet"
        return result, spectra

    table = load_stage(sidecar, path, expect, result)
    if table is not None and result.status != "fail" and "mapping" in sidecar:
        spectra = map_stage(sidecar, table, expect, result)
    elif "mapping" not in sidecar:
        result.stages["map"] = "skipped: no mapping in the sidecar"
    result.stages["export"] = "skipped: export is not built yet"
    return result, spectra


def check_sidecar(sidecar: dict[str, Any], path: Path) -> list[str]:
    """Validate the sidecar's own fields, including the publication confirmation."""
    problems = []
    for key in ("source", "reader", "expect", "publishable"):
        if key not in sidecar:
            problems.append(f"sidecar has no '{key}'")
    publishable = sidecar.get("publishable", {})
    if not isinstance(publishable, dict) or publishable.get("confirmed") is not True:
        problems.append("publication is not confirmed by Rob (publishable.confirmed)")
    source = sidecar.get("source", {})
    for key in ("program_or_instrument", "version", "molecule", "producer"):
        if not isinstance(source, dict) or not source.get(key):
            problems.append(f"sidecar source has no '{key}'")
    return problems


def load_stage(
    sidecar: dict[str, Any], path: Path, expect: dict[str, Any], result: FileResult
) -> Any:
    """Read the file and compare with ``expect.table`` or ``expect.error``."""
    from graphing.core.errors import GraphingError
    from graphing.core.readers.sheet import read_sheet
    from graphing.core.readers.text import ReadSettings, read_text

    settings = ReadSettings(**sidecar.get("settings", {}))
    error_expected = expect.get("error")
    try:
        if sidecar["reader"] == "sheet":
            table = read_sheet(path, sidecar.get("sheet"), settings)
        else:
            table = read_text(path, settings)
    except GraphingError as error:
        if error_expected and error_expected["stage"] == "load":
            if type(error).__name__ == error_expected["type"]:
                result.stages["load"] = (
                    f"pass: failed as expected with {error_expected['type']}"
                )
                return None
            result.fail(
                f"load raised {type(error).__name__}, expected "
                f"{error_expected['type']}: {error}"
            )
        else:
            result.fail(f"load raised {type(error).__name__}: {error}")
        result.stages["load"] = "fail"
        return None

    if error_expected and error_expected["stage"] == "load":
        result.fail(f"load succeeded but {error_expected['type']} was expected")
        result.stages["load"] = "fail"
        return None
    result.stages["load"] = "pass"
    for problem in compare_table(table, expect.get("table", {})):
        result.fail(f"load: {problem}")
    return table


def compare_table(table: Any, expected: dict[str, Any]) -> list[str]:
    """Differences between a read table and the sidecar's ``table`` block."""
    problems = []
    rows, columns = table.data.shape
    if "rows" in expected and rows != expected["rows"]:
        problems.append(f"{rows} rows read, {expected['rows']} expected")
    if "columns" in expected and columns != expected["columns"]:
        problems.append(f"{columns} columns read, {expected['columns']} expected")
    for key, index in (("first", 0), ("last", -1)):
        if key in expected and not np.allclose(
            table.data[index], expected[key], rtol=RTOL, atol=0.0
        ):
            problems.append(
                f"{key} row is {table.data[index].tolist()}, expected {expected[key]}"
            )
    if "header" in expected:
        got = list(table.columns) if table.columns is not None else None
        if got != expected["header"]:
            problems.append(f"header is {got}, expected {expected['header']}")
    for key in ("delimiter", "decimal"):
        if key in expected and getattr(table.settings, key) != expected[key]:
            problems.append(
                f"{key} detected as {getattr(table.settings, key)!r}, "
                f"expected {expected[key]!r}"
            )
    return problems


def map_stage(
    sidecar: dict[str, Any], table: Any, expect: dict[str, Any], result: FileResult
) -> list[Any]:
    """Build spectra from the sidecar's mapping and compare with ``expect.spectra``."""
    from graphing.core.errors import GraphingError
    from graphing.core.readers.mapping import ColumnMapping, build_spectra
    from graphing.core.spectrum import Origin, Technique
    from graphing.core.units import Quantity, Unit

    spec = sidecar["mapping"]
    mapping = ColumnMapping(
        x_column=spec["x_column"],
        y_columns=tuple(spec["y_columns"]),
        x_quantity=Quantity[spec["x_quantity"]],
        x_unit=Unit[spec["x_unit"]],
        y_quantity=Quantity[spec["y_quantity"]],
        technique=Technique[spec["technique"]],
        origin=Origin[spec["origin"]],
    )
    error_expected = expect.get("error")
    try:
        spectra = build_spectra(table, mapping, source=data_path_name(sidecar, result))
    except GraphingError as error:
        if error_expected and error_expected["stage"] == "map":
            if type(error).__name__ == error_expected["type"]:
                result.stages["map"] = (
                    f"pass: failed as expected with {error_expected['type']}"
                )
                return []
            result.fail(
                f"map raised {type(error).__name__}, expected "
                f"{error_expected['type']}: {error}"
            )
        else:
            result.fail(f"map raised {type(error).__name__}: {error}")
        result.stages["map"] = "fail"
        return []
    if error_expected and error_expected["stage"] == "map":
        result.fail(f"map succeeded but {error_expected['type']} was expected")
        result.stages["map"] = "fail"
        return []
    result.stages["map"] = "pass"
    expected = expect.get("spectra", {})
    if "count" in expected and len(spectra) != expected["count"]:
        result.fail(f"map: {len(spectra)} spectra built, {expected['count']} expected")
    if "names" in expected and [s.name for s in spectra] != expected["names"]:
        result.fail(
            f"map: names are {[s.name for s in spectra]}, expected {expected['names']}"
        )
    if "x_reordered" in expected and spectra:
        got = spectra[0].metadata.get("x_reordered") == "yes"
        if got != expected["x_reordered"]:
            result.fail(
                f"map: x_reordered is {got}, expected {expected['x_reordered']}"
            )
    return spectra


@dataclass
class _Named:
    """Stand-in for a quantity or unit in a preview (only ``value`` is read)."""

    value: str


@dataclass
class _PreviewData:
    x: Any
    y: Any
    x_quantity: _Named
    x_unit: _Named
    y_quantity: _Named
    y_unit: _Named


@dataclass
class _StickPreview:
    """Sticks of a parsed program output, drawn as vertical lines in the gallery."""

    name: str
    data: _PreviewData
    sticks: bool = True


def _read_program_output(sidecar: dict[str, Any], path: Path) -> Any:
    """Parse a program output with the reader named in the sidecar."""
    from graphing.core.parsers import orca, turbomole

    reader = sidecar["reader"]
    if reader == "orca":
        if sidecar.get("block", "absorption") == "ir":
            return orca.read_orca_ir(path)
        return orca.read_orca_absorption(path)
    readers = {
        "turbomole-exspectrum": turbomole.read_turbomole_exspectrum,
        "turbomole-escf": turbomole.read_turbomole_escf,
        "turbomole-vibspectrum": turbomole.read_turbomole_vibspectrum,
    }
    return readers[reader](path)


def parse_stage(
    sidecar: dict[str, Any], path: Path, expect: dict[str, Any], result: FileResult
) -> list[Any]:
    """Parse a program output and compare with the sidecar; return a stick preview."""
    from graphing.core.errors import GraphingError

    error_expected = expect.get("error")
    try:
        parsed = _read_program_output(sidecar, path)
    except GraphingError as error:
        if error_expected and error_expected["stage"] == "parse":
            if type(error).__name__ == error_expected["type"]:
                result.stages["parse"] = (
                    f"pass: failed as expected with {error_expected['type']}"
                )
                return []
            result.fail(
                f"parse raised {type(error).__name__}, expected "
                f"{error_expected['type']}: {error}"
            )
        else:
            result.fail(f"parse raised {type(error).__name__}: {error}")
        result.stages["parse"] = "fail"
        return []
    if error_expected and error_expected["stage"] == "parse":
        result.fail(f"parse succeeded but {error_expected['type']} was expected")
        result.stages["parse"] = "fail"
        return []

    if hasattr(parsed, "ir_active"):  # Turbomole vibspectrum: every mode, flagged
        count = len(parsed.mode_index)
        rows = np.column_stack([parsed.wavenumber_cm1, parsed.intensity_km_mol])
        shown = parsed.ir_active & ~parsed.imaginary
        x, y = parsed.wavenumber_cm1[shown], parsed.intensity_km_mol[shown]
        labels = ("wavenumber", "cm⁻¹", "IR intensity", "km mol⁻¹")
        key = "modes"
        if (
            "ir_active_modes" in expect
            and int(parsed.ir_active.sum()) != expect["ir_active_modes"]
        ):
            result.fail(
                f"parse: {int(parsed.ir_active.sum())} IR-active modes, "
                f"{expect['ir_active_modes']} expected"
            )
        if "negative_wavenumbers" in expect:
            got = parsed.wavenumber_cm1[parsed.imaginary].tolist()
            if got != expect["negative_wavenumbers"]:
                result.fail(
                    f"parse: imaginary wave numbers are {got}, "
                    f"expected {expect['negative_wavenumbers']}"
                )
    elif hasattr(parsed, "mode_index"):  # ORCA IR
        count = len(parsed.mode_index)
        rows = np.column_stack([parsed.wavenumber_cm1, parsed.intensity_km_mol])
        x, y = parsed.wavenumber_cm1, parsed.intensity_km_mol
        labels = ("wavenumber", "cm⁻¹", "IR intensity", "km mol⁻¹")
        key = "modes"
    else:  # absorption (ORCA or Turbomole)
        count = len(parsed.fosc)
        columns = [parsed.energy_cm1]
        if parsed.wavelength_nm is not None:
            columns.append(parsed.wavelength_nm)
        rows = np.column_stack([*columns, parsed.fosc])
        x, y = parsed.energy_cm1, parsed.fosc
        labels = ("energy", "cm⁻¹", "oscillator strength", "—")
        key = "transitions"
    if key in expect and count != expect[key]:
        result.fail(f"parse: {count} {key} read, {expect[key]} expected")
    for which, index in (("first", 0), ("last", -1)):
        if which in expect and not np.allclose(
            rows[index], expect[which], rtol=RTOL, atol=0.0
        ):
            result.fail(
                f"parse: {which} row is {rows[index].tolist()}, "
                f"expected {expect[which]}"
            )
    note = "pass"
    if parsed.warnings:
        note += " (" + "; ".join(parsed.warnings) + ")"
    result.stages["parse"] = note if result.status != "fail" else "fail"
    data = _PreviewData(
        x, y, _Named(labels[0]), _Named(labels[1]), _Named(labels[2]), _Named(labels[3])
    )
    return [_StickPreview(path.name, data)]


def _corpus_broadening(technique: Any) -> Any:
    """The broadening the gallery uses (Rob, S019); the app's defaults are the GUI's."""
    from graphing.core.model import Broadening, LineShape
    from graphing.core.spectrum import Technique
    from graphing.core.units import Unit

    if technique is Technique.UV_VIS:
        return Broadening(line_shape=LineShape.GAUSSIAN, fwhm=0.250, fwhm_unit=Unit.EV)
    return Broadening(line_shape=LineShape.LORENTZIAN, fwhm=4.0, fwhm_unit=Unit.CM1)


@dataclass
class _BroadenedPreview:
    """A broadened curve on ε with its sticks, as the evaluation pipeline gives them."""

    name: str
    data: _PreviewData
    stick_x: Any
    stick_y: Any
    caption: str


def broaden_stage(sidecar: dict[str, Any], path: Path, result: FileResult) -> list[Any]:
    """Load through ``core.io``, broaden, convert to ε and check the curve is sane.

    Returns the preview to draw, or an empty list when the stage fails.
    """
    from graphing.core.errors import GraphingError
    from graphing.core.evaluate import layer_values
    from graphing.core.io import load
    from graphing.core.model import Panel
    from graphing.core.operations import add_layer, add_y_transform
    from graphing.core.spectrum import Origin, Technique
    from graphing.core.transforms import (
        IRIntensityToAbsorptivity,
        OscillatorStrengthToAbsorptivity,
    )

    infrared = sidecar["reader"] == "turbomole-vibspectrum" or (
        sidecar["reader"] == "orca" and sidecar.get("block") == "ir"
    )
    technique = Technique.IR if infrared else Technique.UV_VIS
    broadening = _corpus_broadening(technique)
    try:
        spectra = load(path, technique, Origin.THEORETICAL, sidecar["reader"])
        panel = Panel()
        layer = add_layer(panel, spectra[0], broadening=broadening)
        to_epsilon = (
            IRIntensityToAbsorptivity()
            if infrared
            else OscillatorStrengthToAbsorptivity()
        )
        add_y_transform(panel, layer, to_epsilon)
        values = layer_values(layer, panel)
    except GraphingError as error:
        result.fail(f"broaden raised {type(error).__name__}: {error}")
        result.stages["broaden"] = "fail"
        return []
    problems = []
    if not np.all(np.isfinite(values.y)):
        problems.append("the curve has values that are not finite")
    if values.y.size and values.y.min() < 0:
        problems.append("the curve has negative absorptivity")
    if values.sticks is None or values.sticks[0].size == 0:
        problems.append("no sticks are drawn")
    for problem in problems:
        result.fail(f"broaden: {problem}")
    if problems:
        result.stages["broaden"] = "fail"
        return []
    width = f"{broadening.fwhm:g} {broadening.fwhm_unit.value}"
    caption = f"{broadening.line_shape.value}, FWHM {width}"
    result.stages["broaden"] = f"pass ({caption}, {to_epsilon.label})"
    x_axis = panel.x_axis
    assert x_axis is not None and values.sticks is not None
    data = _PreviewData(
        values.x,
        values.y,
        _Named(x_axis.quantity.value),
        _Named(x_axis.unit.value),
        _Named("molar absorptivity"),
        _Named("L mol⁻¹ cm⁻¹"),
    )
    return [
        _BroadenedPreview(path.name, data, values.sticks[0], values.sticks[1], caption)
    ]


def data_path_name(sidecar: dict[str, Any], result: FileResult) -> str:
    """Name used for the source metadata of the spectra."""
    return result.path.name


def figure_name(path: Path, corpus: Path) -> str:
    """A flat, readable figure file name for a corpus file."""
    relative = path.relative_to(corpus).with_suffix("")
    return "-".join(relative.parts) + "-" + path.suffix.lstrip(".") + ".png"


def draw_figure(result: FileResult, spectra: list[Any], target: Path) -> None:
    """Draw the preview of one file; every corpus file gets exactly one figure.

    Until the renderer of E4 exists this is a plain Matplotlib line plot, only meant
    for looking through the corpus. Files that cannot be plotted get a figure that
    says why, so the gallery always has one figure per file.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(figsize=(6, 3.5))
    if spectra:
        for spectrum in spectra:
            if hasattr(spectrum, "stick_x"):  # broadened curve with its sticks
                axes.plot(
                    spectrum.data.x,
                    spectrum.data.y,
                    color="#0A5199",
                    linewidth=1,
                    label=spectrum.caption,
                )
                axes.vlines(
                    spectrum.stick_x, 0, spectrum.stick_y, color="#AA1E1E", linewidth=1
                )
                axes.legend(fontsize=7)
                continue
            if getattr(spectrum, "sticks", False):
                axes.vlines(spectrum.data.x, 0, spectrum.data.y, linewidth=1)
                continue
            axes.plot(
                spectrum.data.x, spectrum.data.y, label=spectrum.name, linewidth=1
            )
        first = spectra[0].data
        axes.set_xlabel(f"{first.x_quantity.value} / {first.x_unit.value}")
        axes.set_ylabel(f"{first.y_quantity.value} / {first.y_unit.value}")
        if len(spectra) > 1:
            axes.legend(fontsize=7)
    else:
        axes.axis("off")
        note = (
            result.messages[0]
            if result.messages
            else next(iter(result.stages.values()), "")
        )
        if result.status == "pass":
            note = " / ".join(v for v in result.stages.values() if v.startswith("pass"))
        axes.text(
            0.5,
            0.5,
            f"{result.path.name}\n{note}",
            ha="center",
            va="center",
            wrap=True,
            fontsize=8,
        )
    axes.set_title(f"{result.path.name} [{result.status}]", fontsize=8)
    figure.tight_layout()
    figure.savefig(target, dpi=110)
    plt.close(figure)


def write_index(results: list[FileResult], gallery: Path) -> None:
    """Write ``index.html`` listing every figure and the stage outcomes."""
    cards = []
    for result in results:
        stages = "".join(
            f"<li>{html.escape(name)}: {html.escape(text)}</li>"
            for name, text in result.stages.items()
        )
        messages = "".join(f"<li><b>{html.escape(m)}</b></li>" for m in result.messages)
        image = f'<img src="{result.figure.name}" width="480">' if result.figure else ""
        cards.append(
            f"<div class='card {result.status}'><h3>{html.escape(result.path.name)} "
            f"[{result.status}]</h3>{image}<ul>{stages}{messages}</ul></div>"
        )
    page = (
        "<!doctype html><meta charset='utf-8'><title>Corpus gallery</title>"
        "<style>body{font-family:sans-serif}.card{display:inline-block;vertical-align:top;"
        "margin:8px;padding:8px;border:2px solid #888;max-width:500px}"
        ".pass{border-color:#007D50}.fail{border-color:#AA1E1E}.skip{border-color:#BF7B00}</style>"
        "<h1>Corpus gallery</h1>" + "".join(cards)
    )
    (gallery / "index.html").write_text(page, encoding="utf-8")


def run_corpus(
    corpus: Path,
    gallery: Path | None,
    progress: Callable[[str], None] | None = None,
) -> list[FileResult]:
    """Run the whole corpus; draw the gallery when ``gallery`` is given."""
    sidecars, orphans = discover(corpus)
    if gallery is not None:
        gallery.mkdir(parents=True, exist_ok=True)
    results: list[FileResult] = []
    for sidecar in sidecars:
        result, spectra = run_file(sidecar, corpus)
        if gallery is not None:
            target = gallery / figure_name(result.path, corpus)
            draw_figure(result, spectra, target)
            result.figure = target
        results.append(result)
        if progress:
            progress(f"{result.status.upper():5} {result.path.relative_to(corpus)}")
    for path in orphans:
        orphan = FileResult(path=path)
        orphan.fail(
            "no sidecar: add a .corpus.json next to it (and Rob's confirmation)"
        )
        if gallery is not None:
            target = gallery / figure_name(path, corpus)
            draw_figure(orphan, [], target)
            orphan.figure = target
        results.append(orphan)
        if progress:
            progress(f"FAIL  {path.relative_to(corpus)}")
    if gallery is not None:
        write_index(results, gallery)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", type=Path, default=ROOT / "tests" / "corpus")
    parser.add_argument(
        "--gallery", type=Path, default=ROOT / "build" / "corpus-gallery"
    )
    parser.add_argument("--no-gallery", action="store_true")
    args = parser.parse_args(argv)
    results = run_corpus(
        args.corpus, None if args.no_gallery else args.gallery, progress=print
    )
    failed = [r for r in results if r.status == "fail"]
    skipped = [r for r in results if r.status == "skip"]
    print(
        f"\n{len(results)} files: {len(results) - len(failed) - len(skipped)} passed, "
        f"{len(skipped)} skipped, {len(failed)} failed."
    )
    for result in failed:
        print(f"\nFAILED: {result.path.relative_to(args.corpus)}")
        for message in result.messages:
            print(f"  - {message}")
    if not args.no_gallery:
        print(f"Gallery: {args.gallery / 'index.html'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
