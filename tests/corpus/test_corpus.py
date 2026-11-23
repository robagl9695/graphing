# SPDX-License-Identifier: GPL-3.0-or-later
"""The corpus harness (T2.4) and the public corpus itself."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.corpus

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests" / "corpus"


def load_harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "run_corpus", ROOT / "tools" / "run_corpus.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_corpus"] = module
    spec.loader.exec_module(module)
    return module


harness = load_harness()
SOURCE = CORPUS / "synthetic" / "uvvis-tab-header.txt"


def copy_with_sidecar(source: Path, folder: Path, name: str | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (name or source.name)
    shutil.copy(source, target)
    sidecar = source.with_name(source.name + ".corpus.json")
    shutil.copy(sidecar, target.with_name(target.name + ".corpus.json"))
    return target


def edit_sidecar(data_file: Path, change: dict[str, object]) -> None:
    path = data_file.with_name(data_file.name + ".corpus.json")
    sidecar = json.loads(path.read_text(encoding="utf-8"))
    for key, value in change.items():
        target = sidecar
        *parents, last = key.split(".")
        for part in parents:
            target = target[part]
        target[last] = value
    path.write_text(json.dumps(sidecar), encoding="utf-8")


def by_name(results: list) -> dict[str, object]:  # type: ignore[type-arg]
    return {r.path.name: r for r in results}


def test_public_corpus_passes() -> None:
    results = harness.run_corpus(CORPUS, None)
    failed = {r.path.name: r.messages for r in results if r.status == "fail"}
    assert failed == {}
    statuses = {r.status for r in results}
    assert "pass" in statuses


def test_corpus_has_the_real_instrument_export() -> None:
    results = by_name(harness.run_corpus(CORPUS, None))
    assert results["hydroquinone-ir-2023-09-04.asc"].status == "pass"  # type: ignore[attr-defined]


def test_adding_a_file_needs_no_code_change(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    copy_with_sidecar(SOURCE, corpus / "a")
    assert len(harness.run_corpus(corpus, None)) == 1
    copy_with_sidecar(SOURCE, corpus / "b", "another-name.txt")
    results = harness.run_corpus(corpus, None)
    assert sorted(r.path.name for r in results) == [
        "another-name.txt",
        "uvvis-tab-header.txt",
    ]
    assert all(r.status == "pass" for r in results)


def test_wrong_sidecar_fails_the_run_and_names_the_file(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    data = copy_with_sidecar(SOURCE, corpus)
    edit_sidecar(data, {"expect.table.rows": 999})
    results = harness.run_corpus(corpus, None)
    assert results[0].status == "fail"
    assert "999 expected" in results[0].messages[0]
    # The command line names the file and exits with status 1.
    code = harness.main(["--corpus", str(corpus), "--no-gallery"])
    assert code == 1


def test_wrong_expected_error_type_fails(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    data = copy_with_sidecar(CORPUS / "synthetic" / "empty.txt", corpus)
    edit_sidecar(data, {"expect.error.type": "AmbiguousFormat"})
    result = harness.run_corpus(corpus, None)[0]
    assert result.status == "fail"
    assert "expected AmbiguousFormat" in result.messages[0]


def test_unexpected_success_when_error_expected_fails(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    data = copy_with_sidecar(SOURCE, corpus)
    edit_sidecar(
        data, {"expect": {"error": {"stage": "load", "type": "NoNumericBlock"}}}
    )
    result = harness.run_corpus(corpus, None)[0]
    assert result.status == "fail"
    assert "succeeded but NoNumericBlock was expected" in result.messages[0]


def test_unconfirmed_publication_fails(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    data = copy_with_sidecar(SOURCE, corpus)
    edit_sidecar(data, {"publishable.confirmed": False})
    result = harness.run_corpus(corpus, None)[0]
    assert result.status == "fail"
    assert "not confirmed" in result.messages[0]


def test_file_without_sidecar_fails(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "loose.txt").write_text("1 2\n3 4\n", encoding="utf-8")
    result = harness.run_corpus(corpus, None)[0]
    assert result.status == "fail"
    assert "no sidecar" in result.messages[0]


def test_stage_not_built_yet_is_skipped_not_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pretend the ORCA parser does not exist yet: its files must be skipped, not failed.
    monkeypatch.setattr(harness, "module_available", lambda name: "parsers" not in name)
    results = by_name(harness.run_corpus(CORPUS, None))
    skipped = results["synthetic-3bands.out"]
    assert skipped.status == "skip"  # type: ignore[attr-defined]
    assert "not built yet" in skipped.messages[0]  # type: ignore[attr-defined]
    assert not [r for r in results.values() if r.status == "fail"]  # type: ignore[attr-defined]


def test_orca_corpus_files_are_parsed_when_the_parser_exists() -> None:
    result = by_name(harness.run_corpus(CORPUS, None))["synthetic-wave.out"]
    assert result.status == "pass"  # type: ignore[attr-defined]
    assert result.stages["parse"].startswith("pass")  # type: ignore[attr-defined]


def test_gallery_has_one_figure_per_file(tmp_path: Path) -> None:
    gallery = tmp_path / "gallery"
    results = harness.run_corpus(CORPUS, gallery)
    figures = sorted(gallery.glob("*.png"))
    assert len(figures) == len(results)
    assert len({r.figure for r in results}) == len(results)
    assert all(figure.stat().st_size > 0 for figure in figures)
    assert (gallery / "index.html").exists()


BROADENED = [
    "synthetic-3bands.out",
    "synthetic-shoulder.out",
    "synthetic-wave.out",
    "artificial.exspectrum",
    "imaginary-mode.vibspectrum",
]


def test_program_outputs_are_broadened_to_epsilon() -> None:
    # E3: every theoretical file that parses is broadened and shown on ε.
    results = by_name(harness.run_corpus(CORPUS, None))
    broadened = sorted(
        name
        for name, r in results.items()
        if r.stages.get("broaden", "").startswith("pass")  # type: ignore[attr-defined]
    )
    assert broadened == sorted(BROADENED)
    for name in BROADENED:
        assert "→ ε" in results[name].stages["broaden"]  # type: ignore[attr-defined]


def test_files_that_must_fail_to_parse_are_not_broadened() -> None:
    results = by_name(harness.run_corpus(CORPUS, None))
    result = results["orca-style-no-block.out"]
    assert result.status == "pass"  # type: ignore[attr-defined]
    assert "broaden" not in result.stages  # type: ignore[attr-defined]
