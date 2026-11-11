"""La vuelta de separacion recorre exactamente los puntos del canesu."""

from __future__ import annotations

import pytest

from engine.garments import generate
from engine.sizes import BODY_SIZES
from engine.spec import Category, Construction, GarmentSpec, PatternParams, Technique


@pytest.mark.parametrize("construction", [Construction.RAGLAN_TOP_DOWN, Construction.YOKE])
@pytest.mark.parametrize("size", list(BODY_SIZES))
def test_division_walks_whole_yoke(construction: Construction, size: str) -> None:
    spec = GarmentSpec(
        categoria=Category.PULLOVER, tecnica=Technique.CIRCULAR, construccion=construction
    )
    pattern = generate(spec, PatternParams(talla=size))
    yoke, body = pattern.section("yoke"), pattern.section("body")
    parts: dict[str, int] = {"knit": 0, "hold": 0, "cast_on": 0}
    for part, n in body.division:
        parts[part] += n
    assert parts["knit"] + parts["hold"] == yoke.end_stitches
    assert parts["knit"] + parts["cast_on"] == body.end_stitches
    holds = [n for part, n in body.division if part == "hold"]
    assert len(holds) == 2 and holds[0] == holds[1]


def test_regular_rows_single_interval() -> None:
    from engine.distribution import regular_rows

    for total in range(1, 140):
        for count in range(0, total + 1):
            rows = regular_rows(total, count)
            assert len(rows) == count
            assert all(1 <= row <= total for row in rows)
            gaps = {b - a for a, b in zip([0, *rows], rows, strict=False)}
            assert len(gaps) <= 1


@pytest.mark.parametrize("construction", [Construction.RAGLAN_TOP_DOWN, Construction.YOKE])
def test_yoke_depth_grades_with_size(construction: Construction) -> None:
    """Regresion: la sisa del raglan caia de 25 a 14 cm entre M y L."""
    spec = GarmentSpec(
        categoria=Category.PULLOVER, tecnica=Technique.CIRCULAR, construccion=construction
    )
    depths = []
    for size in BODY_SIZES:
        pattern = generate(spec, PatternParams(talla=size))
        depths.append({m.key: m.value_cm for m in pattern.measurements}["yoke_depth"])
    assert depths == sorted(depths), depths
