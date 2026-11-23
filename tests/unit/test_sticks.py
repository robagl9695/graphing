# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for X-03: stick lines kept as printed, and display grouping."""

from typing import Any

import numpy as np
import pytest

from graphing.core.data import StickData
from graphing.core.errors import InvalidData, NonPositiveValue
from graphing.core.interval import Interval
from graphing.core.model.style import Style
from graphing.core.region import crop
from graphing.core.sticks import group_sticks
from graphing.core.units import Quantity, Unit


def make(**over: Any) -> StickData:
    args: dict[str, Any] = {
        "x": np.array([3500.25, 3500.15, 1600.0]),
        "y": np.array([1.0, 2.0, 5.0]),
        "x_quantity": Quantity.WAVENUMBER,
        "x_unit": Unit.CM1,
        "y_quantity": Quantity.INTENSITY,
        "y_unit": Unit.ARBITRARY,
    }
    args.update(over)
    return StickData(**args)


def idx(n: int) -> Any:
    return np.arange(n, dtype=np.intp)


def test_sticks_keep_file_order_and_repeats() -> None:
    s = make(x=np.array([300.0, 200.0, 300.0]))
    np.testing.assert_array_equal(s.x, [300.0, 200.0, 300.0])


def test_default_labels_are_numbered_in_file_order() -> None:
    assert make().labels is None
    assert make().line_labels() == ("1", "2", "3")


def test_labels_must_match_lines() -> None:
    with pytest.raises(InvalidData, match="2 labels for 3 lines"):
        make(labels=("a", "b"))


def test_labels_in_equality_and_hash() -> None:
    a, b = make(labels=("a", "b", "c")), make(labels=("a", "b", "c"))
    assert a == b
    assert hash(a) == hash(b)
    assert a != make(labels=("a", "b", "d"))
    assert a != make()
    assert a != make(x=np.array([3500.15, 3500.25, 1600.0]))


def test_style_sum_sticks_default_on() -> None:
    assert Style().sum_sticks is True
    assert Style(sum_sticks=False).sum_sticks is False


def test_crop_sticks_unsorted_keeps_labels() -> None:
    s = make(labels=("a", "b", "c"))
    out = crop(s, Interval(3000.0, 4000.0, Quantity.WAVENUMBER, Unit.CM1))
    np.testing.assert_array_equal(out.x, [3500.25, 3500.15])
    assert out.labels == ("a", "b")


def test_crop_error_uses_min_and_max() -> None:
    from graphing.core.errors import EmptySelection

    with pytest.raises(EmptySelection, match="1600–3500.25"):
        crop(make(), Interval(10.0, 20.0, Quantity.WAVENUMBER, Unit.CM1))


def test_equal_positions_always_sum() -> None:
    x = np.array([100.0, 200.0, 100.0])
    y = np.array([1.0, 4.0, 2.0])
    for flag in (True, False):
        groups = group_sticks(x, y, idx(3), 0.01, flag)
        assert [g.members for g in groups] == [(0, 2), (1,)]
        assert groups[0].height == 3.0
        assert groups[0].degenerate and not groups[0].unresolved
        assert groups[0].position == 100.0


def test_unresolved_lines_sum_at_centroid() -> None:
    x = np.array([3500.15, 3500.25])
    y = np.array([1.0, 3.0])
    (g,) = group_sticks(x, y, idx(2), 1.0)
    assert g.unresolved and not g.degenerate
    assert g.height == 4.0
    assert g.position == pytest.approx((3500.15 + 3 * 3500.25) / 4)


def test_unresolved_separate_when_off_or_zoomed() -> None:
    x = np.array([3500.15, 3500.25])
    y = np.array([1.0, 3.0])
    assert len(group_sticks(x, y, idx(2), 1.0, sum_unresolved=False)) == 2
    assert len(group_sticks(x, y, idx(2), 0.05)) == 2


def test_grouping_is_anchored_without_chaining() -> None:
    x = np.array([0.0, 0.6, 1.2])
    groups = group_sticks(x, np.ones(3), idx(3), 1.0)
    assert [g.members for g in groups] == [(0, 1), (2,)]


def test_zero_sum_uses_tallest_first_in_file_order() -> None:
    x = np.array([10.0, 10.2, 10.4])
    y = np.array([1.0, -1.0, 1.0])
    (g,) = group_sticks(x, y, np.array([5, 4, 3], dtype=np.intp), 1.0)
    assert g.height == 1.0
    y0 = np.array([1.0, -1.0, 0.0])
    (g0,) = group_sticks(x, y0, np.array([7, 2, 9], dtype=np.intp), 1.0)
    assert g0.position == 10.0
    assert g0.members == (2, 7, 9)


def test_zero_sum_tie_picks_lowest_line_index() -> None:
    x = np.array([10.0, 10.2])
    y = np.array([0.0, 0.0])
    (g,) = group_sticks(x, y, np.array([8, 1], dtype=np.intp), 1.0)
    assert g.position == 10.2


def test_empty_input_and_errors() -> None:
    assert group_sticks(np.array([]), np.array([]), idx(0), 1.0) == []
    with pytest.raises(InvalidData, match="same length"):
        group_sticks(np.array([1.0]), np.array([1.0, 2.0]), idx(1), 1.0)
    with pytest.raises(NonPositiveValue):
        group_sticks(np.array([1.0]), np.array([1.0]), idx(1), 0.0)
