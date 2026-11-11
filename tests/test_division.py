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
