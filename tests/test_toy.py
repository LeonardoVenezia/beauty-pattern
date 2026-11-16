"""Juguetes (amigurumi) en piezas: plantillas x grosores x tecnicas."""

from __future__ import annotations

import re
from itertools import product

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from engine.document import build_document
from engine.garments import ImpossibleProportionsError, generate
from engine.garments.toy import DEFAULT_HEIGHT_CM, SECTORS, TEMPLATES
from engine.i18n import t
from engine.ir import Pattern
from engine.serialization import pattern_from_dict, pattern_to_dict
from engine.simulator import simulate
from engine.spec import Category, Figure, GarmentSpec, PatternParams, Technique, YarnWeight
from engine.stitches.kinds import StitchKind
from engine.text import render_document_text, render_pattern_text
from render.pdf import render_pattern_pdf
from render.schematic import render_schematic_svg
from render.toy import render_toy_svg

TECHNIQUES = (Technique.CROCHET, Technique.NEEDLES)


def toy(figure: Figure | None, technique: Technique = Technique.CROCHET) -> GarmentSpec:
    return GarmentSpec(categoria=Category.AMIGURUMI, tecnica=technique, figura=figure)


def craft(pattern: Pattern) -> str:
    return "crochet" if pattern.spec.tecnica is Technique.CROCHET else "knit"


def check_structure(pattern: Pattern, figure: Figure) -> None:
    report = simulate(pattern)
    assert report.ok, [issue.message for issue in report.errors]
    assert pattern.meta.family == "amigurumi"
    ids = [section.id for section in pattern.sections]
    assert ids == [piece.id for piece in TEMPLATES[figure]]
    sectors = SECTORS[craft(pattern)]  # type: ignore[index]
    for section, piece in zip(pattern.sections, TEMPLATES[figure], strict=True):
        assert section.meta["copies"] == piece.copies
        assert section.name_key.endswith("s") == (piece.copies == 2)
        assert section.end_note_keys, section.id
        # Cada pieza crece desde su extremo cerrado en pasos de `sectors` pts.
        counts = [section.start_stitches] + [step.stitch_count_end for step in section.steps]
        assert all(count % sectors == 0 for count in counts[1:])
        if piece.closed:
            assert section.end_stitches == sectors
        if craft(pattern) == "crochet":
            assert section.mode == "round"
            assert section.steps[0].items == (section.steps[0].items[0],)
            assert section.steps[0].expanded_ops()[0].kind is StitchKind.MAGIC_RING
        else:
            assert section.mode == "flat"
            assert section.meta["cast_on_start"] == 1
            assert section.start_stitches == sectors
            # Hileras pares: todo rev, sin cambiar el conteo.
            for step in section.steps:
                if step.number % 2 == 0:
                    assert {op.kind for op in step.expanded_ops()} == {StitchKind.PURL}
    assert pattern.finishing, "falta el armado"


@pytest.mark.parametrize(
    ("figure", "weight", "technique"), list(product(Figure, YarnWeight, TECHNIQUES))
)
def test_every_template_weight_and_technique_simulates(
    figure: Figure, weight: YarnWeight, technique: Technique
) -> None:
    pattern = generate(toy(figure, technique), PatternParams(peso_hilo=weight))
    check_structure(pattern, figure)
    assert not any(w.code.startswith("approx_") for w in pattern.warnings)
    height = {m.key: m for m in pattern.measurements}["toy_height"]
    assert height.target_cm == DEFAULT_HEIGHT_CM[weight]


@settings(max_examples=60, deadline=None)
@given(
    figure=st.sampled_from(list(Figure)),
    weight=st.sampled_from([w for w in YarnWeight if w is not YarnWeight.UNKNOWN]),
    technique=st.sampled_from(TECHNIQUES),
    factor=st.floats(min_value=0.5, max_value=3.0),
)
def test_any_reasonable_height_closes(
    figure: Figure, weight: YarnWeight, technique: Technique, factor: float
) -> None:
    height = DEFAULT_HEIGHT_CM[weight] * factor
    pattern = generate(
        toy(figure, technique),
        PatternParams(peso_hilo=weight, dimensiones_cm={"height": height}),
    )
    check_structure(pattern, figure)
    measured = {m.key: m.value_cm for m in pattern.measurements}
    assert measured["toy_height"] == pytest.approx(height, abs=max(1.5, 0.12 * height))


@pytest.mark.parametrize("technique", TECHNIQUES)
def test_too_small_for_the_yarn_is_rejected(technique: Technique) -> None:
    with pytest.raises(ImpossibleProportionsError):
        generate(
            toy(Figure.BEAR, technique),
            PatternParams(peso_hilo=YarnWeight.SUPER_BULKY, dimensiones_cm={"height": 8.0}),
        )


def test_knit_toy_is_knitted_not_routed_to_crochet() -> None:
    pattern = generate(toy(Figure.BEAR, Technique.NEEDLES), PatternParams())
    assert pattern.spec.tecnica is Technique.NEEDLES
    assert pattern.materials.needle_mm is not None and pattern.materials.hook_mm is None
    machine = generate(toy(Figure.BEAR, Technique.MACHINE), PatternParams())
    assert machine.spec.tecnica is Technique.NEEDLES


def test_unknown_figure_is_a_generic_doll_with_a_note() -> None:
    pattern = generate(toy(None), PatternParams())
    assert [s.id for s in pattern.sections] == ["head", "body", "arm", "leg"]
    assert pattern.meta.title_key == "title.toy_generic"
    assert any(w.code == "toy_generic" for w in pattern.warnings)


def test_golden_crochet_bear_dk() -> None:
    """Osito de crochet en DK, 22 cm (verificado a mano).

    Densidad: 14,5 pb CYC x 1,25 = 18,1 pts y 19,9 vtas / 10 cm.
    Cabeza: contorno pi x 0,52 x 22 = 35,9 cm -> 65 pts -> 66 (multiplo de 6),
    10 vueltas de aumento desde el anillo de 6. Largo de polo a polo
    pi x 0,52 x 22 / 2 = 18 cm -> 36 vueltas: 1 anillo + 10 aum + 15 lisas
    + 10 dism. Cuerpo: pi x 0,38 x 22 = 26,3 cm -> 48 pts; cuello 62 % -> 30.
    """
    pattern = generate(toy(Figure.BEAR), PatternParams())
    assert simulate(pattern).ok
    head = pattern.section("head")
    counts = [step.stitch_count_end for step in head.steps]
    assert counts == [*range(6, 67, 6), *[66] * 15, *range(60, 5, -6)]
    body = pattern.section("body")
    assert body.meta["max_stitches"] == 48 and body.end_stitches == 30
    sizes = {s.id: (s.meta["max_stitches"], s.meta["row_count"]) for s in pattern.sections}
    assert sizes == {
        "head": (66, 36),
        "body": (48, 34),
        "arm": (18, 15),
        "leg": (18, 12),
        "ear": (18, 5),
        "muzzle": (24, 6),
        "tail": (12, 6),
    }
    assert pattern.materials.hook_mm == pytest.approx(3.0)
    finishing = {note.key: note.params for note in pattern.finishing}
    assert finishing["finishing.toy.eyes.crochet"] == {"a": 20, "b": 21, "n": 12, "mm": 12}
    assert finishing["finishing.toy.arms.crochet"] == {"a": 32}
    assert finishing["finishing.toy.legs.crochet"] == {"a": 8, "n": 10}


def test_golden_knit_bear_dk() -> None:
    """Osito de dos agujas en DK: 8 pts montados, +8 por hilera del derecho."""
    pattern = generate(toy(Figure.BEAR, Technique.NEEDLES), PatternParams())
    assert simulate(pattern).ok
    head = pattern.section("head")
    rs = [step.stitch_count_end for step in head.steps if step.number % 2 == 1]
    assert rs[:10] == list(range(16, 89, 8))
    assert head.end_stitches == 8 and head.steps[-1].number % 2 == 1  # se frunce del derecho
    assert {op.kind for op in head.steps[0].expanded_ops()} == {StitchKind.KFB}
    assert pattern.materials.needle_mm == pytest.approx(3.25)


@pytest.mark.parametrize("technique", TECHNIQUES)
def test_text_reads_like_a_toy_pattern(technique: Technique) -> None:
    pattern = generate(toy(Figure.BEAR, technique), PatternParams())
    text = render_document_text(build_document([pattern]))
    expected_parts = (
        "Cabeza",
        "Brazos (tejer 2)",
        "Orejas (tejer 2)",
        "Hocico",
        "Terminación",
        "Ojos:",
        "Piernas:",
        "relleno",
    )
    for expected in expected_parts:
        assert expected in text, expected
    if technique is Technique.CROCHET:
        assert "Vuelta 1: anillo mágico + 6 pb [6 pts]" in text
        assert "Rellenar firme y seguir rellenando" in text
    else:
        assert "Montar 8 puntos." in text
        assert "Hileras pares (revés de la labor)" in text
        assert "Hilera 1: *kfb; rep desde * hasta el final [16 pts]" in text
    assert "Control: esta parte mide" not in text
    english = render_document_text(build_document([pattern], lang="en"))
    assert "Arms (make 2)" in english and "Finishing" in english
    for rendered in (text, english, render_pattern_text(pattern, lang="es")):
        raw_key = re.search(r"\b(?:pattern|finishing|section|warning|notion|measure|title)\.[a-z]", rendered)
        assert raw_key is None, rendered[raw_key.start() - 40 : raw_key.end() + 40] if raw_key else ""


@pytest.mark.parametrize(("figure", "technique"), list(product(Figure, TECHNIQUES)))
def test_schematic_draws_the_assembled_toy(figure: Figure, technique: Technique) -> None:
    pattern = generate(toy(figure, technique), PatternParams())
    svg = render_toy_svg(pattern, "es")
    assert svg == render_schematic_svg(pattern)
    assert "Vista de frente" in svg
    for section in pattern.sections:
        assert t(section.name_key, "es") in svg
    # La cota de altura va a la izquierda del dibujo, no encima.
    match = re.search(r'<text x="([0-9.]+)"[^>]*>Altura</text>', svg)
    assert match is not None and float(match.group(1)) < 200


def test_pdf_and_serialization() -> None:
    pattern = generate(toy(Figure.BUNNY, Technique.NEEDLES), PatternParams())
    assert render_pattern_pdf(pattern).startswith(b"%PDF")
    again = pattern_from_dict(pattern_to_dict(pattern))
    assert again.finishing == pattern.finishing
    assert again.sections == pattern.sections
    assert simulate(again).ok


def test_round_chart_lists_only_pieces_worked_exactly_like_it() -> None:
    """El dibujo de aumentos vale solo para las piezas que se tejen igual,
    vuelta por vuelta: la oreja del gato (con una vuelta pareja en el medio)
    no puede figurar. Y cada vuelta dibuja tantos simbolos como puntos."""
    from engine.blocks import BlockKind
    from engine.document import build_document, growth_rounds
    from engine.stitches.kinds import StitchKind
    from render.crochet_chart import expand
    from render.toy import render_round_chart_svg

    cat = generate(GarmentSpec(categoria=Category.AMIGURUMI, tecnica=Technique.CROCHET, figura="cat"), PatternParams())
    blocks = build_document([cat]).blocks
    at = next(i for i, b in enumerate(blocks) if b.kind is BlockKind.ROUND_CHART)
    assert "Cuerpo" in blocks[at + 1].text and "Orejas" not in blocks[at + 1].text
    for step in growth_rounds(cat.sections[0].steps):
        assert sum(len(expand(item, StitchKind.SC)) for item in step.items) == step.stitch_count_end
    assert "<svg" in (render_round_chart_svg(cat, cat.sections[0].id, "es") or "")
