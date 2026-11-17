"""Ampliacion D037: toda opcion que la IA puede elegir da un patron
verificado (o un rechazo honesto), y si se aproxima, el patron lo dice."""

from __future__ import annotations

import pytest

from engine.garments import GarmentError, generate
from engine.garments.routing import CATEGORY_APPROX
from engine.simulator import simulate
from engine.spec import Category, GarmentSpec, PatternParams, Technique


@pytest.mark.parametrize("category", list(Category))
@pytest.mark.parametrize("technique", [Technique.NEEDLES, Technique.CROCHET])
def test_every_category_gives_a_verified_pattern_or_an_honest_error(category: Category, technique: Technique) -> None:
    try:
        pattern = generate(GarmentSpec(categoria=category, tecnica=technique), PatternParams())
    except GarmentError:
        return
    assert simulate(pattern).ok
    if category in CATEGORY_APPROX:
        assert "approx_category" in {w.code for w in pattern.warnings}
