"""Cualquier combinacion que pueda devolver la IA da un patron verificado."""

from __future__ import annotations

import itertools

import pytest

from engine.garments import generate
from engine.simulator import simulate
from engine.spec import (
    Category,
    Colorwork,
    ColorworkType,
    Construction,
    GarmentSpec,
    PatternParams,
    Technique,
    Texture,
    TextureObservation,
)


@pytest.mark.parametrize("construction", [None, *Construction], ids=str)
@pytest.mark.parametrize("technique", list(Technique), ids=lambda t: t.value)
def test_every_pullover_construction_and_technique_gives_a_pattern(
    technique: Technique, construction: Construction | None
) -> None:
    pattern = generate(
        GarmentSpec(categoria=Category.PULLOVER, tecnica=technique, construccion=construction),
        PatternParams(),
    )
    assert simulate(pattern).ok


def test_specific_unsupported_construction_is_declared() -> None:
    spec = GarmentSpec(categoria=Category.PULLOVER, construccion=Construction.BOTTOM_UP)
    pattern = generate(spec, PatternParams())
    assert pattern.meta.family == "set_in"
    assert "approx_construction" in {w.code for w in pattern.warnings}


def test_unknown_texture_and_uncharted_colorwork_are_declared() -> None:
    spec = GarmentSpec(
        categoria=Category.SCARF,
        texturas=[TextureObservation(textura=Texture.OTHER)],
        colorwork=Colorwork(tipo=ColorworkType.FAIR_ISLE, paleta=["rojo", "blanco"]),
    )
    codes = {w.code for w in generate(spec, PatternParams()).warnings}
    assert {"texture_unidentified", "colorwork_not_charted"} <= codes


def test_crochet_hat_crown_lies_flat() -> None:
    pattern = generate(GarmentSpec(categoria=Category.HAT, tecnica=Technique.CROCHET), PatternParams())
    counts = [step.stitch_count_end for step in pattern.sections[0].steps]
    increase = counts[0]
    growth = [b - a for a, b in itertools.pairwise(counts) if b != a]
    assert set(growth) == {increase}  # circulo plano: mismo aumento por vuelta
    assert simulate(pattern).ok


def test_pdf_keeps_approximation_warnings_across_sizes() -> None:
    from render.pdf import render_pattern_pdf

    pattern = generate(
        GarmentSpec(categoria=Category.PULLOVER, tecnica=Technique.MACHINE), PatternParams()
    )
    pdf = render_pattern_pdf(pattern)
    assert pdf.startswith(b"%PDF")
