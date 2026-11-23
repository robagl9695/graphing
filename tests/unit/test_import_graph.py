# SPDX-License-Identifier: GPL-3.0-or-later
"""The layer rule of CLAUDE.md §6.2, checked on the import statements (T1.6 AC6).

``core/`` imports nothing from ``render/`` or ``gui/`` and no Qt or Matplotlib;
``render/`` imports nothing from ``gui/`` and no Qt.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "graphing"

FORBIDDEN: dict[str, tuple[str, ...]] = {
    "core": ("graphing.render", "graphing.gui", "PySide6", "matplotlib"),
    "render": ("graphing.gui", "PySide6"),
}


def imported_modules(source: str, module: str) -> set[str]:
    """Return the absolute names of every module imported by ``source``."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Resolve a relative import against the importing module's package.
                base = module.split(".")[: -node.level]
                names.add(".".join([*base, node.module] if node.module else base))
            elif node.module:
                names.add(node.module)
    return names


def violations(layer: str) -> list[str]:
    found = []
    for path in sorted((PACKAGE / layer).rglob("*.py")):
        rel = path.relative_to(PACKAGE.parent).with_suffix("")
        module = ".".join(rel.parts)
        for name in imported_modules(path.read_text(encoding="utf-8"), module):
            for banned in FORBIDDEN[layer]:
                if name == banned or name.startswith(banned + "."):
                    found.append(f"{module} imports {name}")
    return found


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_rule(layer: str) -> None:
    assert violations(layer) == []


def test_checker_sees_violations() -> None:
    src = "import matplotlib.pyplot\nfrom ..gui import window\n"
    names = imported_modules(src, "graphing.core.model.axes")
    assert "matplotlib.pyplot" in names
    assert "graphing.core.gui" in names
    names = imported_modules("from ...gui import x\n", "graphing.core.model.axes")
    assert "graphing.gui" in names
