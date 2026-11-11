from __future__ import annotations

import pytest

from engine.spec import StitchPatternName
from engine.stitches.catalog import (
    STITCH_PATTERNS,
    adjust_stitches,
    catalog_id_for_name,
    expand_row,
    get_stitch,
    validate_catalog,
)
from engine.stitches.kinds import StitchKind

REQUIRED = {
    "stockinette",
    "garter",
    "seed",
    "moss",
    "rib_1x1",
    "rib_2x2",
    "rib_3x1",
    "brioche",
    "cable_2x2_front",
    "cable_2x2_back",
    "cable_3x3_front",
    "cable_3x3_back",
    "eyelet",
    "lace_basic",
    "bobbles",
    "honeycomb",
    "crochet_sc",
    "crochet_hdc",
    "crochet_dc",
    "magic_ring",
}


def test_catalog_is_valid() -> None:
    assert validate_catalog() == []


def test_required_patterns_present() -> None:
    assert set(STITCH_PATTERNS) >= REQUIRED


def test_get_stitch() -> None:
    assert get_stitch("stockinette").multiple == 1
    with pytest.raises(KeyError):
        get_stitch("nope")


def test_expand_rows_keep_count() -> None:
    for pattern in STITCH_PATTERNS.values():
        stitches = pattern.multiple * 3
        for row in range(1, pattern.row_repeat + 1):
            ops = expand_row(pattern, stitches, row)
            assert sum(op.consumes for op in ops) == stitches, pattern.id
            assert sum(op.produces for op in ops) == stitches, pattern.id


def test_expand_rejects_bad_multiple() -> None:
    pattern = get_stitch("rib_2x2")
    with pytest.raises(ValueError):
        expand_row(pattern, 6, 1)
    with pytest.raises(ValueError):
        expand_row(pattern, 8, 0)


def test_cable_expansion() -> None:
    pattern = get_stitch("cable_2x2_front")
    ops = expand_row(pattern, 8, 3)
    assert len(ops) == 1
    assert ops[0].kind is StitchKind.CABLE_FRONT
    assert ops[0].width == 4
    assert ops[0].times == 2
    assert ops[0].consumes == 8


def test_round_rows() -> None:
    stockinette = get_stitch("stockinette")
    flat_ops = expand_row(stockinette, 10, 2)
    round_ops = expand_row(stockinette, 10, 2, in_the_round=True)
    assert flat_ops[0].kind is StitchKind.PURL
    assert round_ops[0].kind is StitchKind.KNIT
    rib = get_stitch("rib_1x1")
    assert rib.row_count(in_the_round=True) == 1
    assert rib.row_count(in_the_round=False) == 2


def test_adjust_stitches() -> None:
    assert adjust_stitches(101, 4) == 100
    assert adjust_stitches(102, 4) == 104
    assert adjust_stitches(101, 4, mode="up") == 104
    assert adjust_stitches(1, 4) == 4
    with pytest.raises(ValueError):
        adjust_stitches(10, 0)
    with pytest.raises(ValueError):
        adjust_stitches(10, 2, mode="down")


def test_name_mapping() -> None:
    assert catalog_id_for_name(StitchPatternName.STOCKINETTE) == "stockinette"
    assert catalog_id_for_name(StitchPatternName.CABLES) == "cable_2x2_front"
    assert catalog_id_for_name(StitchPatternName.LACE) == "lace_basic"
    for name in StitchPatternName:
        assert catalog_id_for_name(name) in STITCH_PATTERNS


def test_chart_cells_sum_to_multiple() -> None:
    for pattern in STITCH_PATTERNS.values():
        for row in range(1, pattern.row_repeat + 1):
            cells = pattern.chart_cells(row)
            assert sum(cell.span for cell in cells) == pattern.multiple, (
                pattern.id,
                row,
            )


def test_rib_expands_as_repeat_not_blocks() -> None:
    """Regresion: 1x1 en 80 p es *1 d, 1 r* x40, no 40 d + 40 r."""
    from engine.ir import Repeat

    items = expand_row(get_stitch("rib_1x1"), 80, 1, in_the_round=True)
    assert len(items) == 1
    assert isinstance(items[0], Repeat)
    assert items[0].times == 40
    assert [op.times for op in items[0].ops] == [1, 1]
