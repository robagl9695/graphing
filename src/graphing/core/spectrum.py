# SPDX-License-Identifier: GPL-3.0-or-later
"""Named data (Series) and its specialisation for spectra (Spectrum)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from graphing.core.data import CurveData, StickData
from graphing.core.errors import InvalidData


class Technique(Enum):
    """Spectroscopic technique, declared by the user."""

    UV_VIS = "UV-Vis"
    IR = "IR"


class Origin(Enum):
    """Where the data comes from, declared by the user."""

    THEORETICAL = "theoretical"
    EXPERIMENTAL = "experimental"


@dataclass(frozen=True, kw_only=True)
class Series:
    """Generic named x–y data with read-only metadata.

    Raises
    ------
    InvalidData
        If ``data`` is not curve or stick data, or metadata is not text to text.
    """

    name: str
    data: CurveData | StickData
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.data, (CurveData, StickData)):
            raise InvalidData("data must be CurveData or StickData")
        meta = dict(self.metadata)
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in meta.items()):
            raise InvalidData("metadata keys and values must be text")
        object.__setattr__(self, "metadata", MappingProxyType(meta))

    def __hash__(self) -> int:
        return hash((self.name, self.data, tuple(sorted(self.metadata.items()))))


@dataclass(frozen=True, kw_only=True)
class Spectrum(Series):
    """A series with a declared technique and origin.

    The app never infers or questions either. Sticks imply a theoretical origin.

    Raises
    ------
    InvalidData
        If the data are sticks and the origin is not theoretical.
    """

    technique: Technique
    origin: Origin

    def __post_init__(self) -> None:
        super().__post_init__()
        if isinstance(self.data, StickData) and self.origin is not Origin.THEORETICAL:
            raise InvalidData("stick data can only be a theoretical spectrum")

    def __hash__(self) -> int:
        return hash((super().__hash__(), self.technique, self.origin))
