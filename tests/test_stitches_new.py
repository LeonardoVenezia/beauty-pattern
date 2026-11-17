"""Puntos de la ampliacion (area stitches): cada uno con grafico propio,
conteos que cierran y patrones verificados en varias familias."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from engine.garments import generate
from engine.garments.c2c import c2c_steps, diagonal_blocks
from engine.garments.routing import route
from engine.i18n import CATALOGS, t
from engine.ir import Op, Step, build_step
from engine.simulator import simulate
from engine.spec import (
    Category,
    GarmentSpec,
    PatternParams,
    StitchPatternName,
    Technique,
    YarnWeight,
)
from engine.stitches.catalog import (
    APPROXIMATED_NAMES,
    STITCH_PATTERNS,
    catalog_id_for_name,
    expand_row,
    get_stitch,
    validate_catalog,
)
from engine.stitches.kinds import StitchKind
from render.chart import render_stitch_chart_svg

KNIT = ["reverse_stockinette", "twisted_rib", "broken_rib", "basketweave", "waffle", "linen"]
CROCHET = [
    "crochet_tr",
    "crochet_ribbing",
    "granny_stitch",
    "crochet_linen",
    "v_stitch",
    "shell",
    "filet",
    "tunisian",
    "c2c",
]
WEIGHTS = [YarnWeight.FINGERING, YarnWeight.DK, YarnWeight.WORSTED, YarnWeight.BULKY]


def test_catalog_valid_and_nothing_approximated() -> None:
    assert validate_catalog() == []
    assert frozenset() == APPROXIMATED_NAMES
    for name in [*KNIT, *CROCHET]:
        assert catalog_id_for_name(StitchPatternName(name)) == name


@pytest.mark.parametrize("stitch_id", [*KNIT, *CROCHET])
@given(repeats=st.integers(min_value=1, max_value=60))
def test_rows_keep_count_for_any_width(stitch_id: str, repeats: int) -> None:
    pattern = get_stitch(stitch_id)
    width = repeats * pattern.multiple
    current = width
    for row in range(1, 2 * pattern.row_count() + 1):
        step = build_step(row, current, expand_row(pattern, width, row))
        assert step.stitch_count_end == width
        current = step.stitch_count_end
    if pattern.round_rows is not None:
        for row in range(1, pattern.row_count(in_the_round=True) + 1):
            items = expand_row(pattern, width, row, in_the_round=True)
            assert sum(i.consumes for i in items) == sum(i.produces for i in items) == width


@pytest.mark.parametrize("stitch_id", [*KNIT, *CROCHET])
def test_every_stitch_draws_its_chart(stitch_id: str) -> None:
    pattern = get_stitch(stitch_id)
    for lang in CATALOGS:
        svg = render_stitch_chart_svg(pattern, lang=lang, in_the_round=pattern.round_rows is not None)
        assert svg.startswith("<svg") and "chart." not in svg


def test_flat_and_round_versions_agree() -> None:
    """La hilera del LR vista del LD es la vuelta en redondo (der <-> rev y al revés)."""
    swap = {StitchKind.KNIT: StitchKind.PURL, StitchKind.PURL: StitchKind.KNIT}
    for stitch_id in ["broken_rib", "basketweave", "waffle"]:
        pattern = get_stitch(stitch_id)
        assert pattern.round_rows is not None
        for flat, rnd in zip(pattern.rows[1::2], pattern.round_rows[1::2], strict=True):
            seen = tuple(Op(swap[op.kind], times=op.times) for op in reversed(flat))
            assert seen == rnd


def test_twisted_rib_keeps_columns() -> None:
    rows = get_stitch("twisted_rib").rows
    assert rows[0] == (Op(StitchKind.K1TBL), Op(StitchKind.PURL))
    assert rows[1] == (Op(StitchKind.KNIT), Op(StitchKind.P1TBL))  # LR: el retorcido sigue en su columna


def test_tunisian_row_has_one_return_pass() -> None:
    items = expand_row(get_stitch("tunisian"), 20, 1)
    assert items[-1] == Op(StitchKind.TUNISIAN_RETURN)
    pattern = generate(
        GarmentSpec(categoria=Category.SCARF, tecnica=Technique.CROCHET, punto_base=StitchPatternName.TUNISIAN),
        PatternParams(),
    )
    assert simulate(pattern).ok
    # Sin la pasada de vuelta, el simulador frena el patron.
    section = pattern.sections[0]
    broken = Step(number=2, items=(Op(StitchKind.TSS, times=section.end_stitches),), stitch_count_end=section.end_stitches)
    bad = replace(pattern, sections=(replace(section, steps=(section.steps[0], broken, *section.steps[2:])),))
    assert "tunisian_return" in {issue.code for issue in simulate(bad).errors}


@given(width=st.integers(1, 70), height=st.integers(1, 70))
@settings(max_examples=150)
def test_c2c_diagonals_follow_the_rectangle(width: int, height: int) -> None:
    steps = c2c_steps(width, height)
    assert len(steps) == width + height - 1
    current = 0
    for row, step in enumerate(steps, start=1):
        assert step.consumes == current
        assert step.stitch_count_end == diagonal_blocks(row, width, height)
        current = step.stitch_count_end
    assert steps[-1].stitch_count_end == 1
    # Cada bloque se teje una vez: la suma de bloques nuevos + bloques sobre
    # bloques es el area del rectangulo.
    made = sum(
        op.produces for step in steps for op in step.expanded_ops() if op.kind in {StitchKind.C2C_NEW, StitchKind.C2C_BLOCK}
    )
    assert made == width * height


_KNIT_FAMILIES = [
    Category.SCARF,
    Category.BLANKET,
    Category.HAT,
    Category.MITTENS,
    Category.SHAWL,
    Category.BAG,
    Category.OTHER,
    Category.PULLOVER,
]
_CROCHET_FAMILIES = [
    Category.SCARF,
    Category.BAG,
    Category.COWL,
    Category.SHAWL,
    Category.OTHER,
    Category.PULLOVER,
    Category.CARDIGAN,
    Category.VEST,
]


@pytest.mark.parametrize("stitch_id", KNIT)
@given(
    category=st.sampled_from(_KNIT_FAMILIES),
    weight=st.sampled_from(WEIGHTS),
    width=st.floats(10, 120),
)
@settings(max_examples=25, deadline=None)
def test_knit_stitches_simulate_in_families(stitch_id: str, category: Category, weight: YarnWeight, width: float) -> None:
    spec = GarmentSpec(categoria=category, tecnica=Technique.NEEDLES, punto_base=StitchPatternName(stitch_id))
    params = PatternParams(peso_hilo=weight, dimensiones_cm={"width": width, "length": 60.0})
    pattern = generate(spec, params)
    report = simulate(pattern)
    assert report.ok, report.errors
    assert "approx_stitch" not in {w.code for w in pattern.warnings}


@pytest.mark.parametrize("stitch_id", CROCHET)
@given(
    category=st.sampled_from(_CROCHET_FAMILIES),
    weight=st.sampled_from(WEIGHTS),
    width=st.floats(10, 120),
    size=st.sampled_from(["XS", "M", "2XL"]),
)
@settings(max_examples=25, deadline=None)
def test_crochet_stitches_simulate_in_families(
    stitch_id: str, category: Category, weight: YarnWeight, width: float, size: str
) -> None:
    spec = GarmentSpec(categoria=category, tecnica=Technique.CROCHET, punto_base=StitchPatternName(stitch_id))
    params = PatternParams(peso_hilo=weight, talla=size, dimensiones_cm={"width": width, "length": 50.0})
    pattern = generate(spec, params)
    report = simulate(pattern)
    assert report.ok, report.errors


def test_rectangles_use_the_stitch_and_its_gauge() -> None:
    linen = generate(
        GarmentSpec(categoria=Category.SCARF, punto_base=StitchPatternName.LINEN), PatternParams()
    )
    plain = generate(GarmentSpec(categoria=Category.SCARF), PatternParams())
    assert linen.params.densidad is not None and plain.params.densidad is None
    # ASUNCION de densidad del punto lino: mas pts y muchas mas hileras.
    assert linen.sections[0].end_stitches > plain.sections[0].end_stitches
    assert len(linen.sections[0].steps) > 1.5 * len(plain.sections[0].steps)
    kinds = {op.kind for step in linen.sections[0].steps for op in step.expanded_ops()}
    assert {StitchKind.SL1_WYIF, StitchKind.SL1_WYIB} <= kinds


def test_crochet_ribbing_is_worked_sideways() -> None:
    pattern = generate(
        GarmentSpec(categoria=Category.SCARF, tecnica=Technique.CROCHET, punto_base=StitchPatternName.CROCHET_RIBBING),
        PatternParams(dimensiones_cm={"width": 20, "length": 150}),
    )
    section = pattern.sections[0]
    gauge = pattern.params.densidad
    assert gauge is not None
    # La cadena base va a lo largo (150 cm) y las hileras dan el ancho.
    assert section.start_stitches == 0 and abs(section.end_stitches / gauge.stitches_per_cm - 150) < 1.5
    assert abs(section.meta["row_count"] / gauge.rows_per_cm - 20) < 1.0


def test_shell_text_and_glossary() -> None:
    from engine.text import render_pattern_text

    pattern = generate(
        GarmentSpec(categoria=Category.SCARF, tecnica=Technique.CROCHET, punto_base=StitchPatternName.SHELL),
        PatternParams(),
    )
    text = render_pattern_text(pattern)
    assert "abanico" in text and "5 pa en el mismo pt" in text and "saltar 2" in text


def test_routing_no_longer_approximates_stitches() -> None:
    for name in [*KNIT, *CROCHET]:
        _, notes = route(GarmentSpec(categoria=Category.SCARF, punto_base=StitchPatternName(name)))
        assert "stitch" not in notes


def test_seed_and_moss_are_unambiguous_in_every_language() -> None:
    seed = STITCH_PATTERNS["seed"].name_key
    moss = STITCH_PATTERNS["moss"].name_key
    double = {"es": "doble", "en": "double", "fr": "double", "de": "doppelt", "it": "doppio"}
    for lang in CATALOGS:
        assert t(seed, lang) != t(moss, lang)
        assert double[lang] in t(moss, lang).casefold()
    # En ingles, el "moss" britanico es el seed americano: se aclara.
    assert "UK: moss" in t(seed, "en")
    # En Espana "punto musgo" es el punto bobo: el punto arroz doble no se llama asi.
    assert "musgo" not in t(moss, "es")


def test_document_draws_the_base_stitch() -> None:
    from engine.document import build_document

    for tech, name in ((Technique.NEEDLES, "basketweave"), (Technique.CROCHET, "v_stitch")):
        pattern = generate(GarmentSpec(categoria=Category.SCARF, tecnica=tech, punto_base=StitchPatternName(name)), PatternParams())
        document = build_document([pattern])
        assert [c.id for c in document.charts] == [name]


@pytest.mark.parametrize("stitch_id", CROCHET)
def test_crochet_hat_falls_back_honestly(stitch_id: str) -> None:
    """El gorro de crochet va en redondo con aumentos: los puntos con grupos
    se reemplazan por el mas parecido y se avisa. (Los saltos de 6-12 pts del
    gorro de crochet en talles extremos son de la familia gorro, no del punto.)"""
    spec = GarmentSpec(categoria=Category.HAT, tecnica=Technique.CROCHET, punto_base=StitchPatternName(stitch_id))
    pattern = generate(spec, PatternParams())
    assert simulate(pattern).ok
    assert "stitch_fallback_round" in {w.code for w in pattern.warnings}
