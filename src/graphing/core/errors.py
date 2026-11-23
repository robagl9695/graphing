# SPDX-License-Identifier: GPL-3.0-or-later
"""Named errors of the core. All derive from :class:`GraphingError`."""


class GraphingError(Exception):
    """Base class of every error raised on purpose by graphing."""


class NonPositiveValue(GraphingError):
    """A value that must be finite and strictly positive is not."""


class IncompatibleXQuantity(GraphingError):
    """Two x quantities cannot be converted into one another."""


class InvalidData(GraphingError):
    """Arrays or fields of a data object break one of its invariants."""


class InvalidUnit(GraphingError):
    """A unit does not belong to the quantity it is paired with."""


class CannotNormalise(GraphingError):
    """A normalisation has no valid reference value."""


class InvalidTransform(GraphingError):
    """A transform cannot be applied to this y quantity or these values."""


class DivisionByZero(GraphingError):
    """A transform would divide by zero."""


class InvalidInterval(GraphingError):
    """An interval or a pair of view limits is not valid."""


class EmptySelection(GraphingError):
    """A selection or crop leaves too few points."""


class IncompatibleYQuantity(GraphingError):
    """Layers with different y quantities would share a y axis not normalised."""


class YChoiceRequired(GraphingError):
    """A layer needs the user's choice (normalise or double y axis) to be added."""


class StackedWithDualAxis(GraphingError):
    """A stacked y side cannot coexist with a second y axis."""


class NestedInset(GraphingError):
    """An inset cannot contain an inset."""


class RegionInBreak(GraphingError):
    """A zoom region lies inside an axis break."""


class GridOverlap(GraphingError):
    """Two cells of a canvas grid overlap."""


class MissingBroadening(GraphingError):
    """A stick layer has no broadening parameters."""


class FeatureNotAvailable(GraphingError):
    """The feature exists in the model but is not available in this version."""


class EmptyPanel(GraphingError):
    """The operation needs a panel with at least one layer."""


class UnknownItem(GraphingError):
    """A layer, inset or canvas is not part of the container it was looked up in."""


class UnreadableFile(GraphingError):
    """A file is missing, cannot be opened or cannot be decoded."""


class NoNumericBlock(GraphingError):
    """A text file has no block of numeric rows to read."""


class AmbiguousFormat(GraphingError):
    """The delimiter and decimal separator cannot be told apart from the file."""


class InvalidMapping(GraphingError):
    """A column mapping does not fit the table it is applied to."""


class NonNumericCells(GraphingError):
    """Columns chosen for a spectrum hold values that are not finite numbers."""


class MalformedCell(GraphingError):
    """A data row is broken by a missing or non-numeric cell inside the table."""


class MissingBlock(GraphingError):
    """A program output does not contain the block that was asked for."""


class MalformedBlock(GraphingError):
    """A block of a program output is broken or has a layout that is not recognised."""


class UnknownFormat(GraphingError):
    """No file format could be chosen from the declaration or the file name."""
