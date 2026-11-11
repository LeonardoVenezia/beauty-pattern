"""Paneles de textura en el cuerpo: verificados, legibles y con grafico."""

from __future__ import annotations

import pytest

from engine.blocks import BlockKind
from engine.document import build_document
from engine.garments import generate, generate_size_set
from engine.garments.panels import round_rows, texture_motif
from engine.simulator import simulate
from engine.sizes import BODY_SIZES
from engine.spec import Category, Construction, GarmentSpec, PatternParams, Technique, YarnWeight
from engine.stitches.catalog import get_stitch
from engine.stitches.kinds import StitchKind
from engine.text import render_pattern_text
from render.chart import render_stitch_chart_svg

TEXTURES = ["cables", "lace", "bobbles", "honeycomb"]


def sweater(texture: str, construction: Construction = Construction.RAGLAN_TOP_DOWN) -> GarmentSpec:
    return GarmentSpec(
        categoria=Category.PULLOVER,
        tecnica=Technique.CIRCULAR,
        construccion=construction,
        texturas=[{"textura": texture}],
    )


@pytest.mark.parametrize("construction", [Construction.RAGLAN_TOP_DOWN, Construction.YOKE])
@pytest.mark.parametrize("texture", TEXTURES)
@pytest.mark.parametrize("weight", [YarnWeight.FINGERING, YarnWeight.DK, YarnWeight.BULKY])
def test_panels_simulate_in_every_size(construction, texture, weight) -> None:  # type: ignore[no-untyped-def]
    for size in BODY_SIZES:
        pattern = generate(sweater(texture, construction), PatternParams(talla=size, peso_hilo=weight))
        assert simulate(pattern).ok, (size, texture)
        body = pattern.section("body")
        assert "panel_rows" in body.meta


def test_cable_rounds_in_the_round_are_knit_not_purl() -> None:
    """Regresion: la hilera del reves 'P4' en redondo se teje al derecho."""
    rows = round_rows(get_stitch("cable_2x2_front"))
    assert rows[1][0].kind is StitchKind.KNIT


def test_texture_text_uses_markers_and_chart() -> None:
    text = render_pattern_text(generate(sweater("cables"), PatternParams(talla="M")))
    assert "gráfico 1" in text
    assert "pts de panel" in text
    assert "2/2 CF, 2 rev, 2/2 CF" not in text  # no se escribe punto por punto


def test_document_has_chart_and_cable_abbreviation() -> None:
    document = build_document(generate_size_set(sweater("cables"), PatternParams()), highlight="M")
    kinds = [b.kind for b in document.blocks]
    assert BlockKind.CHART in kinds
    assert len(document.charts) == 1
    glossary = next(b for b in document.blocks if b.kind is BlockKind.TABLE and b.rows[0][0] == "pts")
    assert "CF" in [label for label, _ in glossary.rows]


def test_chart_draws_each_repeat_side_by_side() -> None:
    svg = render_stitch_chart_svg(get_stitch("stockinette"), repeats=3)
    assert ">3<" in svg  # numeracion de puntos
    assert 'stroke="#c0392b"' in svg  # recuadro de la repeticion


def test_plain_photo_has_no_panel() -> None:
    spec = GarmentSpec(categoria=Category.PULLOVER, tecnica=Technique.CIRCULAR)
    assert texture_motif(spec) is None
    assert "panel_rows" not in generate(spec, PatternParams()).section("body").meta
