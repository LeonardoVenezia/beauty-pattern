from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from engine.distribution import (
    decrease_evenly,
    even_positions,
    increase_evenly,
    paired_decreases,
    split_even,
)
from engine.stitches.kinds import StitchKind


@settings(max_examples=300)
@given(total=st.integers(min_value=0, max_value=500), parts=st.integers(min_value=1, max_value=40))
def test_split_even_properties(total: int, parts: int) -> None:
    groups = split_even(total, parts)
    assert len(groups) == parts
    assert sum(groups) == total
    assert max(groups) - min(groups) <= 1
    # Simetria perfecta solo cuando el resto se puede repartir en pares
    # (o cuando no hay resto).
    if parts % 2 == 1 or total % parts % 2 == 0:
        assert groups == list(reversed(groups))


@settings(max_examples=200)
@given(total=st.integers(min_value=1, max_value=500), count=st.integers(min_value=1, max_value=100))
def test_even_positions_in_range_and_sorted(total: int, count: int) -> None:
    if count > total:
        return
    positions = even_positions(total, count)
    assert len(positions) == count
    assert positions == sorted(positions)
    assert all(1 <= p <= total for p in positions)


def test_split_even_examples() -> None:
    assert split_even(10, 4) == [2, 3, 3, 2]
    assert split_even(9, 3) == [3, 3, 3]
    assert split_even(100, 3) == [33, 34, 33]


def test_increase_evenly_consumes_and_produces() -> None:
    ops, end = increase_evenly(100, 4)
    assert end == 104
    assert sum(op.consumes for op in ops) == 100
    assert sum(op.produces for op in ops) == 104
    assert sum(1 for op in ops if op.kind in {StitchKind.M1L, StitchKind.M1R}) == 4
    assert ops[0].kind == StitchKind.KNIT


@settings(max_examples=300)
@given(
    stitches=st.integers(min_value=2, max_value=400),
    increases=st.integers(min_value=0, max_value=100),
)
def test_increase_properties(stitches: int, increases: int) -> None:
    if increases > stitches:
        return
    ops, end = increase_evenly(stitches, increases)
    assert sum(op.consumes for op in ops) == stitches
    assert sum(op.produces for op in ops) == stitches + increases
    assert end == stitches + increases


def test_decrease_evenly_consumes_and_produces() -> None:
    ops, end = decrease_evenly(100, 10)
    assert end == 90
    assert sum(op.consumes for op in ops) == 100
    assert sum(op.produces for op in ops) == 90
    assert sum(1 for op in ops if op.kind == StitchKind.K2TOG) == 10


@settings(max_examples=300)
@given(
    stitches=st.integers(min_value=2, max_value=400),
    decreases=st.integers(min_value=0, max_value=100),
)
def test_decrease_properties(stitches: int, decreases: int) -> None:
    if decreases * 2 > stitches:
        return
    ops, end = decrease_evenly(stitches, decreases)
    assert sum(op.consumes for op in ops) == stitches
    assert sum(op.produces for op in ops) == stitches - decreases
    assert end == stitches - decreases


def test_paired_decreases() -> None:
    ops, end = paired_decreases(80, 2, 2)
    assert end == 76
    assert sum(op.consumes for op in ops) == 80
    assert sum(op.produces for op in ops) == 76
    kinds = [op.kind for op in ops]
    assert StitchKind.SSK in kinds
    assert StitchKind.K2TOG in kinds


def test_invalid_distribution() -> None:
    with pytest.raises(ValueError):
        split_even(10, 0)
    with pytest.raises(ValueError):
        even_positions(10, 11)
    with pytest.raises(ValueError):
        increase_evenly(0, 1)
    with pytest.raises(ValueError):
        decrease_evenly(10, 6)
    with pytest.raises(ValueError):
        paired_decreases(10, 4, 4)
